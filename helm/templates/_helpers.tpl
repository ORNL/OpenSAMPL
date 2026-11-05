{{/* Base name */}}
{{- define "opensampl.name" -}}
opensampl
{{- end -}}

{{/* Full release-qualified name */}}
{{- define "opensampl.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" (include "opensampl.name" .) .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end -}}

{{/* Component-specific name */}}
{{- define "opensampl.componentname" -}}
{{- printf "%s-%s" (include "opensampl.name" .) .component | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/* Common labels */}}
{{- define "opensampl.labels" -}}
app.kubernetes.io/name: {{ include "opensampl.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .component }}
app.kubernetes.io/component: {{ .component }}
{{- end }}
{{- end -}}
