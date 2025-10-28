{{/* Common naming helpers */}}
{{- define "opensampl.name" -}}
opensampl
{{- end -}}


{{- define "opensampl.fullname" -}}
{{ include "opensampl.name" . }}-{{ .Release.Name }}
{{- end -}}


{{- define "opensampl.labels" -}}
app.kubernetes.io/name: {{ include "opensampl.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}