/// <reference types="miniprogram-api-typings" />

// wx.cloud 在部分基础库 typings 中缺失，这里补全 callContainer 所需的最小声明
declare namespace WechatMiniprogram.Wx {
  interface CallContainerOption {
    config?: { env?: string };
    path: string;
    method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" | "HEAD" | "OPTIONS";
    data?: string | Record<string, any>;
    header?: Record<string, string>;
    success?: (res: { data: any; statusCode: number; header: Record<string, string> }) => void;
    fail?: (err: { errMsg: string }) => void;
    complete?: () => void;
  }
}

declare namespace WechatMiniprogram {
  interface Cloud {
    init(option?: { env?: string; traceUser?: boolean }): void;
    callContainer(option: Wx.CallContainerOption): void;
  }
}
