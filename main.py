from straregy.binance_liquidation_shield import LiquidationShield

# if __name__ == "__main__":
#     sentinel = LiquidationShield()
#     sentinel.start()

# from strategy.binance_liquidation_shield import LiquidationShield
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/health')
def health_check():
    return 'Service is up and running!'

def start_liquidation_shield():
    import os 
    print(f'API_KEY: {os.getenv("BINANCE_API_KEY")}')
    print(f'SECRET_KEY: {os.getenv("BINANCE_SECRET_KEY")}')
    sentinel = LiquidationShield()
    sentinel.start()

if __name__ == "__main__":
    # 啟動 LiquidationShield 作為單獨的執行緒
    thread = threading.Thread(target=start_liquidation_shield)
    thread.start()
    
    # 啟動 Flask 伺服器來處理健康檢查
    app.run(host='0.0.0.0', port=8080)
