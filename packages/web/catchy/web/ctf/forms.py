from __future__ import annotations

import tarfile
from typing import Any

from django import forms
from django.utils.text import slugify
from omegaconf import OmegaConf

from .models import AgentConfiguration, Challenge, Ctf, Secret


class SecretForm(forms.ModelForm):
    class Meta:
        model = Secret
        fields = ["name", "label", "value", "allowed_groups"]
        widgets = {"value": forms.PasswordInput(render_value=True)}


class AgentConfigurationForm(forms.ModelForm):
    class Meta:
        model = AgentConfiguration
        fields = ["name", "slug", "yaml", "view_groups", "use_groups"]
        widgets = {"yaml": forms.Textarea(attrs={"rows": 22, "cols": 100})}

    def __init__(self, *args: Any, user=None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_yaml(self) -> str:
        yaml = self.cleaned_data["yaml"]
        try:
            AgentConfiguration(yaml=yaml).resolved_mapping(user=self.user)
        except Exception as exc:
            raise forms.ValidationError(f"invalid agent YAML: {exc}") from exc
        return yaml


class CtfForm(forms.ModelForm):
    settings_yaml = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 8, "cols": 80}),
        help_text="Optional YAML mapping for future CTF-level settings.",
    )

    class Meta:
        model = Ctf
        fields = ["title", "slug", "description", "view_groups", "init_groups"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["settings_yaml"].initial = self.instance.settings

    def clean_settings_yaml(self) -> str:
        value = str(self.cleaned_data.get("settings_yaml", ""))
        _clean_yaml_mapping(value)
        return value

    def save(self, commit: bool = True) -> Ctf:
        instance = super().save(commit=False)
        instance.settings = self.cleaned_data["settings_yaml"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ChallengeForm(forms.ModelForm):
    webhook_url = forms.URLField(
        required=False,
        label="Webhook URL",
        help_text="Endpoint the agent can POST to during the run. Leave blank to disable.",
        widget=forms.URLInput(attrs={"placeholder": "https://example.com/hook"}),
    )
    webhook_preferred_language = forms.CharField(
        required=False,
        label="Preferred language",
        help_text="Spoken language the agent should respond in (e.g. English, 한국어). Optional.",
        widget=forms.TextInput(attrs={"placeholder": "English"}),
    )
    config_yaml = forms.CharField(
        required=False,
        label="Config (YAML)",
        help_text="Free-form YAML mapping forwarded to the challenge runner.",
        widget=forms.Textarea(attrs={"rows": 8, "cols": 80}),
    )

    fieldsets = [
        ("Basics", ["challenge_id", "description", "source_archive"]),
        ("Webhook", ["webhook_url", "webhook_preferred_language"]),
        ("Advanced", ["config_yaml"]),
    ]

    class Meta:
        model = Challenge
        fields = ["challenge_id", "description", "source_archive"]
        help_texts = {
            "description": "Markdown is supported.",
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            webhook_data = _safe_yaml_mapping(self.instance.webhook)
            self.fields["webhook_url"].initial = webhook_data.get("url", "")
            self.fields["webhook_preferred_language"].initial = webhook_data.get(
                "preferred_language", ""
            )
            self.fields["config_yaml"].initial = self.instance.config
            self.fields["source_archive"].required = False
            self.fields[
                "source_archive"
            ].help_text = "Leave blank to keep the existing archive."

    def clean_source_archive(self):
        archive = self.cleaned_data.get("source_archive")
        if not archive:
            if self.instance.pk and self.instance.source_archive:
                return self.instance.source_archive
            raise forms.ValidationError("This field is required.")
        if not hasattr(archive, "name"):
            return archive
        name = archive.name.lower()
        if not (name.endswith(".tar.gz") or name.endswith(".tgz")):
            raise forms.ValidationError("source must be a .tar.gz or .tgz archive")
        try:
            archive.file.seek(0)
            with tarfile.open(fileobj=archive.file, mode="r:gz"):
                pass
        except tarfile.TarError as exc:
            raise forms.ValidationError("source archive is not a valid tar.gz") from exc
        finally:
            archive.file.seek(0)
        return archive

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        url = (cleaned.get("webhook_url") or "").strip()
        lang = (cleaned.get("webhook_preferred_language") or "").strip()
        if lang and not url:
            self.add_error(
                "webhook_url",
                "Webhook URL is required when a preferred language is set.",
            )
        return cleaned

    def clean_config_yaml(self) -> str:
        value = str(self.cleaned_data.get("config_yaml", ""))
        _clean_yaml_mapping(value)
        return value

    def save(self, commit: bool = True) -> Challenge:
        instance = super().save(commit=False)
        instance.webhook = self._serialize_webhook()
        instance.config = self.cleaned_data["config_yaml"]
        if commit:
            instance.save()
        return instance

    def _serialize_webhook(self) -> str:
        url = (self.cleaned_data.get("webhook_url") or "").strip()
        lang = (self.cleaned_data.get("webhook_preferred_language") or "").strip()
        if not url:
            return ""
        payload: dict[str, Any] = {"url": url}
        if lang:
            payload["preferred_language"] = lang
        return OmegaConf.to_yaml(OmegaConf.create(payload))


class ThreadCreateForm(forms.Form):
    name = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "bright-cipher-0427"}),
    )
    agent = forms.ModelChoiceField(queryset=AgentConfiguration.objects.none())

    def __init__(
        self,
        *args: Any,
        user,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        agent_ids = [
            agent.pk
            for agent in AgentConfiguration.objects.prefetch_related("use_groups")
            if agent.can_use(user)
        ]
        self.fields["agent"].queryset = AgentConfiguration.objects.filter(
            pk__in=agent_ids
        )

    def clean_name(self) -> str:
        value = self.cleaned_data.get("name", "")
        if not value:
            return ""
        name = slugify(value)[:80]
        if not name:
            raise forms.ValidationError("Enter a name with letters or numbers.")
        return name


def _clean_yaml_mapping(value: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    try:
        data = OmegaConf.to_container(OmegaConf.create(value), resolve=True)
    except Exception as exc:
        raise forms.ValidationError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise forms.ValidationError("YAML value must be a mapping")
    return {str(key): item for key, item in data.items()}


def _safe_yaml_mapping(value: str) -> dict[str, Any]:
    if not value or not value.strip():
        return {}
    try:
        data = OmegaConf.to_container(OmegaConf.create(value), resolve=True)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): item for key, item in data.items()}
