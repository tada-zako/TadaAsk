# LunarCache Upgrade Guide

## 升级前

升级前先运行 `lunarcache backup --manifest`，生成当前缓存与命名空间的备份清单。

确认备份清单写入成功后，再停止服务并安装新版本。升级过程不要求删除原有缓存目录。
