import { createApp } from "./app";
import { CONFIG } from "./config";

const app = createApp();

const server = app.listen(CONFIG.port, CONFIG.host, () => {
  console.log(`🌫️ DhuanAlert Backend API listening at http://${CONFIG.host}:${CONFIG.port}`);
  console.log(`   - Environment: ${process.env.NODE_ENV || "development"}`);
  console.log(`   - ML Model Bridge: ${CONFIG.mlModelDir}`);
  console.log(`   - Runs Persistence: ${CONFIG.runsDir}`);
});

process.on("SIGTERM", () => {
  console.log("SIGTERM received, shutting down gracefully...");
  server.close(() => {
    console.log("Process terminated.");
  });
});
