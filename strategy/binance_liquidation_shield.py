import os
import time
import pandas as pd
import pytz
from datetime import datetime
from enum import Enum
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()

from gateway.binance_api import BinanceSpotHttp, BinanceUSDFeatureHttp
from gateway.binance_api import AcountType

# TODO: 用 logging 不要用 print
# TODO: 新增去槓桿參數
# TODO: 對衝 Sui, Solana 2 倍槓桿, 鏈上質押, 找到一個平衡點

class AdjustmentSide(Enum):
    ADD = "ADD"
    REDUCE = "REDUCE"


class CurrentAsset(Enum):
    USDT = "USDT"


class LiquidationShield:

    def __init__(self):
        """
        Args:
            adjustment_threshold (float): 當可調整額度達到此閥值, 才開始進行調整
            patrol_frequency (float): 多久巡邏一次要不要調整
            cooldown_period (float): 發生 Error 時, 要停幾秒
            buffer_amount (Decimal): 為了避免時間差, 加入一些調整保證金的 buffer_amount

        Warning:
            目前取回活期存款 API 有 3 秒的限制, 所以 patrol_frequency 建議不要低於 3
        """
        self.feature_http_client = BinanceUSDFeatureHttp()
        self.spot_http_client = BinanceSpotHttp()

        self.adjustment_threshold = Decimal(os.getenv("ADJUSTMENT_THRESHOLD", "3.0"))
        self.patrol_frequency = float(os.getenv("PATROL_FREQUENCY", "3.5"))
        self.cooldown_period = float(os.getenv("COOLDOWN_PERIOD", "1.0"))
        self.buffer_amount = Decimal(os.getenv("BUFFER_AMOUNT", "1.0"))
        self.ltv_limit = Decimal(os.getenv("LTV_LIMIT", "0.7"))
        self.demand_product_id = { # 活期存款的產品代碼
            "USDT": "USDT001",
        }

    def _collect_margin(self, target_asset: str, adjustment_amount: Decimal):
        """ 
        從各個地方湊到所需的保證金, 並放到現貨帳戶, 
        保證金來源於三道防線 (現貨帳戶 -> 活存帳戶 -> BTC 借貸), 當前一道防線被突破才會進到下一道防線

        Args:
            target_asset (str): 要調整的 asset
            adjustment_amount (Decimal): 總共要湊齊的數量

        Return:
            success (bool): 是否有成功湊齊
            message (str): 相關訊息
            lack_amount (Decimal): 缺少的數量, 距離湊齊還差多少
        """
        message = None

        # Defense 1: 現貨帳戶 ==============================================================================================================
        account_information = self.spot_http_client.get_account_information(omitZeroBalances=True)
        account_balance = account_information['balances'] 
        target_account_balance = [asset for asset in account_balance if asset["asset"] == target_asset]

        if target_account_balance: # 確認現貨帳戶是否有資料

            # 現貨帳戶現有的資產
            free_balance = Decimal(target_account_balance[0]["free"])
            
            # 如果現貨的錢足夠 cover, 就直接執行然後結束
            if free_balance >= adjustment_amount:
                return {"success": True, "message": message, "lack_amount": Decimal("0")}
                
            # 如果不夠, 則計算還需要轉多少
            else:
                adjustment_amount = adjustment_amount - free_balance

        print(f"現貨額度不足, 缺少 {adjustment_amount}U")

        # Defense 2: 活存帳戶 ==============================================================================================================
        flexible_position = self.spot_http_client.get_flexible_product_position(asset=target_asset)
        flexible_position = [asset for asset in flexible_position["rows"] if asset["productId"] == self.demand_product_id[target_asset]]

        if flexible_position: # 確認有活期存款資料再執行下去
            flexible_position = flexible_position[0]
            flexible_position_totalAmount = Decimal(flexible_position["totalAmount"])

            # 計算可贖回 amount
            if flexible_position_totalAmount >= adjustment_amount:
                redeem_amount = adjustment_amount
            else:
                redeem_amount = flexible_position_totalAmount

            # 開始贖回活期存款, 並轉到現貨帳戶
            self.spot_http_client.redeem_flexible_product(
                productId=flexible_position["productId"],
                amount=redeem_amount,
                destAccount=AcountType.SPOT.value
            )

            # 計算還需多少保證金
            adjustment_amount = adjustment_amount - redeem_amount
            if adjustment_amount == Decimal("0"):
                return {"success": True, "message": message, "lack_amount": adjustment_amount}
        
        print(f"活存額度不足, 缺少 {adjustment_amount}U")

        # Defense 3: BTC 借貸 ==============================================================================================================
        ongoing_loan = self.spot_http_client.get_flexible_loan_ongoing_orders(collateralCoin="BTC", loanCoin=target_asset)
        ongoing_loan = ongoing_loan["rows"][0]
        current_ltv = Decimal(ongoing_loan["currentLTV"])

        if current_ltv < self.ltv_limit: # 確認目前質押率還在可控範圍再借 

            # 計算在可控範圍內還可借多少 U
            ltv_per_u = Decimal(ongoing_loan["currentLTV"]) / Decimal(ongoing_loan["totalDebt"])
            available_loan = (self.ltv_limit - current_ltv) / ltv_per_u

            if available_loan >= adjustment_amount:
                loan_amount = adjustment_amount
            else:
                loan_amount = available_loan

            self.spot_http_client.flexible_loan_borrow(
                loan_coin=target_asset,
                loan_amount=loan_amount, 
                collateral_coin="BTC"
            )

            # 計算還需多少保證金
            adjustment_amount = adjustment_amount - loan_amount
            if adjustment_amount == Decimal("0"):
                return {"success": True, "message": message, "lack_amount": adjustment_amount}

        return {"success": False, "message": message, "lack_amount": adjustment_amount}
    
    def _add_position_margin(self, symbol: str, adjustment_amount: Decimal, target_asset: str):
        """
        增加逐倉合約保證金. From 現貨帳戶 to 逐倉帳戶

        Args:
            symbol (str): 要調整的逐倉交易
            adjustment_amount (Decimal): 要調整的數量
            target_asset (str): 目標調整 asset
        """

        # 從現貨帳戶轉到合約帳戶
        self.spot_http_client.new_future_account_transfer(
            asset=target_asset, amount=adjustment_amount, type=1)
        
        # 從合約帳戶轉到目標逐倉帳戶
        self.feature_http_client.modify_isolated_position_margin(
            symbol=symbol, amount=adjustment_amount, type=1)

        return {"success": True}

    def _reduce_position_margin(self, symbol: str, adjustment_amount: Decimal, target_asset: str) -> dict:
        """ 
        減少逐倉合約保證金, 並轉到現貨帳戶, 等時間到系統會自動轉活存

        Args:
            symbol (str): 要調整的逐倉交易
            adjustment_amount (Decimal): 要調整的數量
            target_asset (str): 調整的 asset
        """
 
        # Step 1: 提取到合約帳戶
        self.feature_http_client.modify_isolated_position_margin(
            symbol=symbol, amount=adjustment_amount, type=2)
        
        # Step 2: 提取到現貨帳戶
        self.spot_http_client.new_future_account_transfer(
            asset=target_asset, amount=adjustment_amount, type=2)

        return {"success": True}
    
    def _get_positions_for_adjustment(self) -> pd.DataFrame:

        # 掃描現有倉位狀態, 並轉為 dataframe
        account_info = self.feature_http_client.get_account_information_v2()
        my_positions = [position for position in account_info["positions"] if Decimal(position["positionAmt"]) != 0]
        df_positions = pd.DataFrame(my_positions)

        # 計算可調整額度
        df_positions["adjustment_limit"] = df_positions.apply(
            lambda position: \
                Decimal(position["isolatedWallet"]) - Decimal(position["initialMargin"]) + Decimal(position["unrealizedProfit"]),
            axis=1)
        
        # 確認調整資產是 USDT or USDC
        df_positions["asset"] = df_positions["symbol"].apply(
            lambda x: CurrentAsset.USDT.value if x.endswith(CurrentAsset.USDT.value) else CurrentAsset.USDC.value)
        
        # 確認保證金調整方向
        df_positions["adjustment_side"] = df_positions["adjustment_limit"].apply(
            lambda x: AdjustmentSide.ADD.value if x < 0 else AdjustmentSide.REDUCE.value)

        # 確認調整倉為並扣除 buffrt
        df_positions["adjustment_limit"] = df_positions["adjustment_limit"].apply(
            lambda x: abs(x) - self.buffer_amount)
        
        # print 不需調整的 position
        df_show = df_positions[df_positions["adjustment_limit"] < self.adjustment_threshold]
        df_show.apply(
            lambda row: print(f'{row["symbol"]} 預計調整 {row["adjustment_limit"]}{row["asset"]} 保證金, 未達門檻暫時不作動'),
            axis=1)
        
        # 移除調整幅度過小的 position
        df_positions_for_adjustment = df_positions[df_positions["adjustment_limit"] > self.adjustment_threshold]
        df_positions_for_adjustment = df_positions_for_adjustment.reset_index(drop=True)

        return df_positions_for_adjustment

    def _start_patrol(self):

        df_positions_for_adjustment = self._get_positions_for_adjustment()

        # 減少保證金
        df_reduce_mergin = df_positions_for_adjustment[df_positions_for_adjustment["adjustment_side"] == AdjustmentSide.REDUCE.value]
        if df_reduce_mergin.empty is False:
            
            # TODO: 目前用 for 迴圈是為了要保證執行的維持, 可找其他方案優化
            for _, row in df_reduce_mergin.iterrows():
                self._reduce_position_margin(
                    symbol=row["symbol"], 
                    adjustment_amount=row["adjustment_limit"],
                    target_asset=row["asset"])
                print(f'{row["symbol"]} 減少 {row["adjustment_limit"]}{row["asset"]} 保證金')
        
        # 增加保證金
        df_add_mergin = df_positions_for_adjustment[df_positions_for_adjustment["adjustment_side"] == AdjustmentSide.ADD.value]
        if df_add_mergin.empty is False:

            # 把所有需要的保證金先轉到現貨帳戶
            total_add_amount = df_add_mergin["adjustment_limit"].sum()
            response = self._collect_margin(
                target_asset=CurrentAsset.USDT.value, 
                adjustment_amount=total_add_amount)
            
            # 開始調整
            if response["success"] is True: # 資源足夠, 開始進行調整

                # TODO: 目前用 for 迴圈是為了要保證執行的維持, 可找其他方案優化
                for _, row in df_add_mergin.iterrows():
                    self._add_position_margin(
                        symbol=row["symbol"], 
                        adjustment_amount=row["adjustment_limit"], 
                        target_asset=row["asset"])
                    
                    print(f'{row["symbol"]} 增加 {row["adjustment_limit"]}{row["asset"]} 保證金')

            else: 
                print(f'本次調整還缺少 {response["lack_amount"]}{row["asset"]} 保證金')
                # TODO: 如果保證金真的不夠, 要有排序跟比例給最緊急的 position 最多
                # 考慮是要全保還是放棄單一

        # TODO: 監控帳戶狀態, ex 借款 LTV, 目前活存金額, 總槓桿數
         
        return None

        # Step 2: 開始逐一判斷是否需要調整
        for position in my_positions:

            # 計算可調整額度
            symbol=position["symbol"]
            adjustment_limit = \
                Decimal(position["isolatedWallet"]) - Decimal(position["initialMargin"]) + Decimal(position["unrealizedProfit"])

            # 如果調整幅度夠大, 則開始調整
            if adjustment_limit > self.adjustment_threshold:

                adjustment_limit = adjustment_limit - self.buffer_amount
                self._reduce_position_margin(
                    symbol=symbol,
                    adjustment_amount=adjustment_limit
                )

                print(f"{symbol} 減少 {adjustment_limit}U 保證金")

            elif adjustment_limit < -self.adjustment_threshold:
                
                adjustment_limit = abs(adjustment_limit) - self.buffer_amount
                response = self._add_position_margin(
                    symbol=symbol,
                    adjustment_amount=adjustment_limit
                )

                print(f"{symbol} 增加 {adjustment_limit}U 保證金")
                if response["message"]:
                    print(response["message"])

            else:
                print(f'本次調整未觸發, 原預計幅度為 {adjustment_limit}')

    def start(self):
        while True:
            try:
                start_time = time.time()

                print("====================== START ======================")
                print(f"開始時間: {datetime.now(pytz.timezone('Asia/Singapore')).strftime('%Y-%m-%d %H:%M:%S')}")
                self._start_patrol()
                print(f"執行時間： {time.time() - start_time:.3f} sec.")
                print("======================= END =======================\n")
                
                time.sleep(self.patrol_frequency)

            except Exception as e:
                print(f"Error: {e}")
                time.sleep(self.cooldown_period)


if __name__ == "__main__":
    sentinel = LiquidationShield()
    sentinel.start()


        # while True:
            # pol_orderbook = self.http_client.get_orderbook(symbol="POLUSDT")
            # print(pol_orderbook)
            # matic_orderbook = self.http_client.get_orderbook(symbol="MATICUSDT")
            # print(matic_orderbook)
            # time.sleep(1)
            
            # print(float(matic_orderbook["a"][0][0]) - float(pol_orderbook["a"][0][0]))
            # print(float(pol_orderbook["b"][0][0]) - float(matic_orderbook["b"][0][0]))

            # print("====================")
            # print("====================")