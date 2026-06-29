import { client } from "../client";

/**
 * Admin 登录请求 payload
 */
interface LoginAdminPayload {
  username: string;
  password: string;
}

/** Admin 登录相关接口 */
export const authApi = {
  /** 使用 OAuth2 password form 登录 */
  login: (body: LoginAdminPayload) =>
    client.POST("/admin/auth/login", {
      body: {
        username: body.username,
        password: body.password,
        scope: "",
      },
      bodySerializer: (formBody) => {
        const form = new URLSearchParams();

        // 后端 OAuth2PasswordRequestForm 需要表单格式，
        // 需要将 JSON body 转换为表单形式
        for (const [key, value] of Object.entries(formBody)) {
          if (value !== null && value !== undefined) {
            form.set(key, String(value));
          }
        }

        return form.toString();
      },
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    }),
};
