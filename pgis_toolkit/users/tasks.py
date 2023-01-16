
from celery import Celery, shared_task


@shared_task(bind=True, max_retries=3, soft_time_limit=800)
def check_token_expiration(self):
    try:
        print('****checking token expiration for preliminary users****')
        from datetime import datetime, timezone

        from pgis_toolkit.users.models import PreliminaryUser
        pre_user_objs = PreliminaryUser.active.filter(status='Pending').values('id', 'email_verification_token', 'last_updated')
        current_datetime = datetime.now().replace(tzinfo=timezone.utc)
        threshold = 7
        for obj in pre_user_objs:
            time_diff = current_datetime - obj['last_updated']
            if time_diff.days >= threshold:
                pre_user_instance = PreliminaryUser.active.get(id=obj['id'])
                pre_user_instance.status = 'Expired'
                pre_user_instance.save()
        print('Task Completed')
    except Exception as e:
        return("Task fail, error: " + str(e))
