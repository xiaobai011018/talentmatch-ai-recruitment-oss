"""
----------------------------------------------------
 File Name:        retry_config
 Author:           hoges
 Created Date:     2025/9/28
 Last Modified:    2025/9/28
 Python Version:   
----------------------------------------------------
"""
# 最大重试次数
HTTP_RETRY_TIMES = 3
# 重试间隔时间（秒）
HTTP_RETRY_GAP = 1

# requests 超时配置：(连接超时, 读取超时)，避免外部接口长时间不返回导致任务卡死
HTTP_TIMEOUT = (5, 60)
