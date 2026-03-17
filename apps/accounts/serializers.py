from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers


User = get_user_model()


class TokenLoginSerializer(serializers.Serializer):
    login = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        login = attrs["login"].strip()
        password = attrs["password"]
        username = login

        if "@" in login:
            try:
                username = User.objects.get(email__iexact=login).username
            except User.DoesNotExist as exc:
                raise serializers.ValidationError("Invalid credentials.") from exc

        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=password,
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials.")

        attrs["user"] = user
        return attrs


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "company_name",
            "preferred_language",
            "account_type",
            "plan_tier",
            "is_superuser",
        )
