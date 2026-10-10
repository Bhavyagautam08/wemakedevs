import { Request, Response, NextFunction } from "express";

export class ApiError extends Error {
  public statusCode: number;
  public code: string;

  constructor(statusCode: number, code: string, message: string) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
  }
}

export function errorHandler(err: any, req: Request, res: Response, next: NextFunction) {
  if (err instanceof ApiError || (Number.isInteger(err?.statusCode) && typeof err?.code === "string")) {
    return res.status(err.statusCode).json({
      error: { code: err.code, message: err.message },
    });
  }

  console.error("Unhandled API Error:", err);
  return res.status(500).json({
    error: {
      code: "INTERNAL_ERROR",
      message: err.message || "An unexpected internal server error occurred.",
    },
  });
}
