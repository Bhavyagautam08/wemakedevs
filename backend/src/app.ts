import express, { Express, Request, Response, NextFunction } from "express";
import cors from "cors";
import { apiRouter } from "./routes";
import { errorHandler, ApiError } from "./middleware/errorHandler";
import { CONFIG } from "./config";

export function createApp(): Express {
  const app = express();

  // CORS Middleware
  app.use(
    cors({
      origin: (origin, callback) => {
        // Allow requests with no origin (e.g. mobile apps, curl, server-to-server)
        if (!origin) {
          return callback(null, true);
        }

        // Allow any localhost, 127.0.0.1, or configured origins
        const isAllowed =
          origin === CONFIG.corsOrigin ||
          origin.startsWith("http://localhost:") ||
          origin.startsWith("http://127.0.0.1:") ||
          origin.startsWith("http://[::1]:") ||
          origin === "http://localhost" ||
          origin === "http://127.0.0.1";

        if (isAllowed) {
          callback(null, true);
        } else {
          callback(null, false);
        }
      },
      methods: ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
      allowedHeaders: ["Content-Type", "Authorization", "X-Requested-With"],
      credentials: true,
    }),
  );

  // Body parser
  app.use(express.json({ limit: "10mb" }));
  app.use(express.urlencoded({ extended: true, limit: "10mb" }));

  // Routes
  app.use("/", apiRouter);

  // 404 Catch-all
  app.use((req: Request, res: Response, next: NextFunction) => {
    next(new ApiError(404, "NOT_FOUND", `Endpoint '${req.method} ${req.path}' was not found.`));
  });

  // Global Error Handler
  app.use(errorHandler);

  return app;
}
