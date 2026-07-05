import { client } from "./client";
import type { components } from "@/shared/api/generated/schema";

// 从 OpenAPI schema 提取的 provider/model 类型别名
export type ModelProfileCreatePayload =
  components["schemas"]["ModelProfileCreate"];
export type ModelProfileRead = components["schemas"]["ModelProfileRead"];
export type ModelProfileUpdatePayload =
  components["schemas"]["ModelProfileUpdate"];
export type ProviderCreatePayload =
  components["schemas"]["ProviderCreateWithModels"];
export type ProviderRead = components["schemas"]["ProviderRead"];
export type ProviderUpdatePayload = components["schemas"]["ProviderUpdate"];
export type ProviderWithModelsRead =
  components["schemas"]["ProviderWithModelProfilesRead"];

/** Admin Console provider-model CRUD 接口。 */
export const providerModelApi = {
  // === Provider ===
  listProviders: () => client.GET("/admin/model-profile/provider/list"),

  listProvidersWithModels: () =>
    client.GET("/admin/model-profile/provider/list/models"),

  listEnabledProvidersWithModels: () =>
    client.GET("/admin/model-profile/provider/list/models/enabled"),

  createProvider: (body: ProviderCreatePayload) =>
    client.POST("/admin/model-profile/provider/new", { body }),

  updateProvider: (providerUid: string, body: ProviderUpdatePayload) =>
    client.PATCH("/admin/model-profile/provider/{provider_uid}", {
      params: { path: { provider_uid: providerUid } },
      body,
    }),

  deleteProvider: (providerUid: string) =>
    client.DELETE("/admin/model-profile/provider/{provider_uid}", {
      params: { path: { provider_uid: providerUid } },
    }),

  // === Model Profile ===
  createModel: (providerUid: string, body: ModelProfileCreatePayload) =>
    client.POST("/admin/model-profile/provider/{provider_uid}/models/new", {
      params: { path: { provider_uid: providerUid } },
      body,
    }),

  getModel: (providerUid: string, modelUid: string) =>
    client.GET(
      "/admin/model-profile/provider/{provider_uid}/models/{model_uid}",
      {
        params: {
          path: { provider_uid: providerUid, model_uid: modelUid },
        },
      },
    ),

  updateModel: (
    providerUid: string,
    modelUid: string,
    body: ModelProfileUpdatePayload,
  ) =>
    client.PATCH(
      "/admin/model-profile/provider/{provider_uid}/models/{model_uid}",
      {
        params: {
          path: { provider_uid: providerUid, model_uid: modelUid },
        },
        body,
      },
    ),

  deleteModel: (providerUid: string, modelUid: string) =>
    client.DELETE(
      "/admin/model-profile/provider/{provider_uid}/models/{model_uid}",
      {
        params: {
          path: { provider_uid: providerUid, model_uid: modelUid },
        },
      },
    ),
};
