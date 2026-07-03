import type {
  SourceItemProcessStatus,
  SourceProcessStatus,
} from "@/console/api/sources";
import { translate as t } from "@/console/i18n";
import type { RAGJobStatus, SourceTone, SourceType } from "./source-types";

export type SourceDisplayNamespace = "sources" | "project";

export function sourceTypeLabel(
  sourceType: SourceType,
  namespace: SourceDisplayNamespace = "sources",
): string {
  return t(`${displayRoot(namespace)}.sourceType.${sourceType}`);
}

export function sourceStatusLabel(
  status: SourceProcessStatus,
  namespace: SourceDisplayNamespace = "sources",
): string {
  return t(`${displayRoot(namespace)}.sourceStatus.${status}`);
}

export function sourceVisibilityLabel(
  isPublic: boolean,
  namespace: SourceDisplayNamespace = "sources",
): string {
  return isPublic
    ? t(`${displayRoot(namespace)}.visibility.public`)
    : t(`${displayRoot(namespace)}.visibility.private`);
}

export function sourceItemStatusLabel(status: SourceItemProcessStatus): string {
  const labels: Record<SourceItemProcessStatus, string> = {
    completed: t("sources.service.itemStatus.completed"),
    failed: t("sources.service.itemStatus.failed"),
    pause_requested: t("sources.service.itemStatus.pause_requested"),
    paused: t("sources.service.itemStatus.paused"),
    pending: t("sources.service.itemStatus.pending"),
    processing: t("sources.service.itemStatus.processing"),
  };

  return labels[status];
}

export function sourceJobStatusLabel(status: RAGJobStatus): string {
  const labels: Record<RAGJobStatus, string> = {
    cancelled: t("sources.service.jobStatus.cancelled"),
    completed: t("sources.service.jobStatus.completed"),
    failed: t("sources.service.jobStatus.failed"),
    queued: t("sources.service.jobStatus.queued"),
    running: t("sources.service.jobStatus.running"),
  };

  return labels[status];
}

export function sourceStatusTone(status: SourceProcessStatus): SourceTone {
  if (status === "completed") {
    return "success";
  }

  if (status === "failed") {
    return "danger";
  }

  if (status === "processing" || status === "pause_requested") {
    return "warning";
  }

  return "muted";
}

export function sourceItemStatusTone(
  status: SourceItemProcessStatus,
): SourceTone {
  if (status === "completed") {
    return "success";
  }

  if (status === "failed") {
    return "danger";
  }

  if (status === "processing" || status === "pause_requested") {
    return "warning";
  }

  return "muted";
}

export function sourceJobStatusTone(status: RAGJobStatus): SourceTone {
  if (status === "completed") {
    return "success";
  }

  if (status === "failed" || status === "cancelled") {
    return "danger";
  }

  if (status === "queued" || status === "running") {
    return "warning";
  }

  return "muted";
}

function displayRoot(namespace: SourceDisplayNamespace): string {
  return namespace === "project" ? "project.service" : "sources.service";
}
