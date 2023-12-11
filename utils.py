from io import BytesIO
from traceback import format_exc
from typing import Optional
from .models.results import TaskResults
from .models.tasks import Task
from pylon.core.tools import log

from tools import api_tools, rpc_tools, data_tools, MinioClient, VaultClient, MinioClientAdmin, LokiLogFetcher, constants as c


def write_task_run_logs_to_minio_bucket(task_result: TaskResults, task_name: Optional[str] = None, **kwargs):
    if not task_name:
        task_name = Task.query.filter(Task.task_id == task_result.task_id).first().task_name

    logs_query = '{hostname="%s", task_id="%s", task_result_id="%s"}' % (task_name, task_result.task_id, task_result.task_result_id)
    enc = 'utf-8'
    file_output = BytesIO()
    file_output.write(f'Task {task_name} (task_result_id={task_result.task_result_id}) run log:\n'.encode(enc))

    llf = LokiLogFetcher.from_project(task_result.project_id)
    try:
        llf.fetch_logs(query=logs_query)
        llf.to_file(file_output, enc=enc)
    except:
        log.warning('Request to log storage failed, using logs from task result. Request error: %s', format_exc())
        try:
            file_output.write(task_result.log.encode(enc))
        except:
            pass
        file_output.seek(0)

    # integration_id = report.test_config.get(
    #     'integrations', {}).get('system', {}).get('s3_integration', {}).get('integration_id')
    # is_local = report.test_config.get(
    #     'integrations', {}).get('system', {}).get('s3_integration', {}).get('is_local')

    bucket_name = str(task_name).replace("_", "").replace(" ", "").lower()

    if task_result.mode == 'default':
        minio_client = MinioClient.from_project_id(task_result.project_id)  # todo: handle integration s3
    else:
        minio_client = MinioClientAdmin()

    if bucket_name not in minio_client.list_bucket():
        minio_client.create_bucket(bucket=bucket_name, bucket_type='autogenerated', retention_days=c.BUCKET_RETENTION_DAYS)
    minio_client.upload_file(bucket_name, file_output, f"{task_result.task_result_id}.log")
