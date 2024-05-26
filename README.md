# liquidation-shield

## TODO

- 降低 Docker 大小

## Deploy

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
