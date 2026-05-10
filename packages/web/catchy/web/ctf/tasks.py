from django.tasks import task

from .services import run_thread_sync


@task
def run_thread(thread_id: int) -> None:
    run_thread_sync(thread_id)
