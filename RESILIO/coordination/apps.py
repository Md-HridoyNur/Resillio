from django.apps import AppConfig


class CoordinationConfig(AppConfig):
    name = "coordination"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.contrib.auth.signals import user_logged_out
        from .models import Profile

        def clear_presence(sender, request, user, **kwargs):
            if user:
                Profile.objects.filter(user=user).update(
                    last_seen=None,
                    share_location=False,
                    latitude=None,
                    longitude=None,
                    location_accuracy=None,
                    location_updated_at=None,
                )

        user_logged_out.connect(
            clear_presence, dispatch_uid="resilio-clear-presence", weak=False
        )
