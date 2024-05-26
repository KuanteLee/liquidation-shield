# liquidation-shield

## TODO

- 降低 Docker 大小

## GCP Deploy

(Fail: Binance 禁止美國 API Request, 目前 Cloud Run 全部是從美國總部發出 Request
可能解法: 要額外設 GCP VCP, 但有額外費用, 且較不穩定, 待研究)

Step 1: 從 GCP 編譯器 Clone 目前的 Code

- https://console.cloud.google.com/artifacts?referrer=search&cloudshell=true&hl=zh-TW&project=laplace-plan&supportedpurview=project

Step 2: Build docker image and push, 刪除舊的 Image

- docker image build --tag asia-east1-docker.pkg.dev/laplace-plan/liquidation-shield/myimage:tag1 .
- docker run --rm -it asia-east1-docker.pkg.dev/laplace-plan/liquidation-shield/myimage:tag1 .
- docker push asia-east1-docker.pkg.dev/laplace-plan/liquidation-shield/myimage:tag1

Step 3: Deploy to Cloud Run

## Reference

GCP Cloud Run Deploy: https://www.practiceprobs.com/blog/2022/12/15/how-to-schedule-a-python-script-with-docker-and-google-cloud/#__tabbed_2_1
-> Issue: https://www.googlecloudcommunity.com/gc/Infrastructure-Compute-Storage/Google-Cloud-Function-IP-Address-setting/m-p/495097
-> Solution: https://dev.binance.vision/t/service-unavailable-from-a-restricted-location/13813

requests.exceptions.ConnectionError
-> https://blog.csdn.net/weixin_45520735/article/details/115260374
