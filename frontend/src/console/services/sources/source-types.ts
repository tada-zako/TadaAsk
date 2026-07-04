import type {
  RAGJobRead,
  RAGJobStartResponse,
  SourceCreatePayload,
  SourceItemProcessStatus,
  SourceItemRead,
  SourceProcessStatus,
  SourceRead,
} from "@/console/api/sources";
import type { components } from "@/shared/api/generated/schema";

export type SourceType = SourceRead["sourceType"];
export type SourceTone = "success" | "warning" | "danger" | "muted";
export type SourceItemsRouteName = "source-items";
export type RAGJobStatus = components["schemas"]["RAGJobStatus"];
export type RAGJobType = components["schemas"]["RAGJobType"];
export type WebCrawlConfigInput = components["schemas"]["WebCrawlConfig-Input"];
export type WebCrawlConfigOutput =
  components["schemas"]["WebCrawlConfig-Output"];

// 创建数据源的表单输入载荷。
export type CreateSourceInput = Omit<SourceCreatePayload, "status">;

// 知识库管理主列表中的行数据结构。
export interface SourceRow {
  uid: string;
  name: string;
  sourceType: SourceType;
  typeLabel: string;
  isPublic: boolean;
  visibilityLabel: string;
  visibilityTone: "success" | "muted";
  status: SourceProcessStatus;
  statusLabel: string;
  statusTone: SourceTone;
  lastUpdatedLabel: string;
  createdLabel: string;
  itemsRouteName: SourceItemsRouteName | null;
  source: SourceRead;
}

// 知识库详情子项列表行展示模型。
export interface SourceItemRow {
  uid: string;
  title: string;
  sourceType: SourceType;
  filename: string | null;
  originUrl: string | null;
  displayOrigin: string;
  status: SourceItemProcessStatus;
  statusLabel: string;
  statusTone: SourceTone;
  createdLabel: string;
  updatedLabel: string;
  progress: number | null;
  showProgress: boolean;
  canIndex: boolean;
  canPause: boolean;
  canResume: boolean;
  canRename: boolean;
  canDelete: boolean;
  canDownload: boolean;
  sourceItem: SourceItemRead;
}

export interface SourceListWorkspaceViewModel {
  sources: SourceRead[];
  sourceRows: SourceRow[];
}

export interface SourceWorkspaceViewModel {
  source: SourceRead;
  sourceRow: SourceRow;
  sourceItemRows: SourceItemRow[];
}

export interface SourceJobViewModel {
  jobUid: string;
  jobType: RAGJobType;
  sourceUid: string;
  sourceItemUids: string[];
  status: RAGJobStatus;
  statusLabel: string;
  statusTone: SourceTone;
  createdLabel: string;
  startedLabel: string;
  finishedLabel: string;
  error: string | null;
  job: RAGJobRead | RAGJobStartResponse;
}

export interface SourceWorkspaceOptions {
  itemProgressByUid?: Record<string, number | null | undefined>;
}
