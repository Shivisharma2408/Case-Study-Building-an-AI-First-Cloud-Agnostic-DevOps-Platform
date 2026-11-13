{{- define "idea-board.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "idea-board.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else if contains (include "idea-board.name" .) .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "idea-board.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "idea-board.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/name: {{ include "idea-board.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: idea-board
idea-board/environment: {{ .Values.environment }}
{{- end -}}

{{/* selectorLabels: call with (dict "ctx" $ "component" "backend") */}}
{{- define "idea-board.selectorLabels" -}}
app.kubernetes.io/name: {{ include "idea-board.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "idea-board.dbSecretName" -}}
{{- if .Values.database.embedded.enabled -}}
{{- printf "%s-db" (include "idea-board.fullname" .) -}}
{{- else -}}
{{- required "database.existingSecret is required unless database.embedded.enabled" .Values.database.existingSecret -}}
{{- end -}}
{{- end -}}

{{- define "idea-board.podSecurityContext" -}}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "idea-board.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{/* topologySpread: call with (dict "ctx" $ "component" "backend") */}}
{{- define "idea-board.topologySpread" -}}
{{- if .ctx.Values.topologySpread.enabled }}
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        {{- include "idea-board.selectorLabels" . | nindent 8 }}
{{- end }}
{{- end -}}
