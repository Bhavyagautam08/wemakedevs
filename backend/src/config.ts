import path from "node:path";
import dotenv from "dotenv";

dotenv.config();

export const BACKEND_ROOT = path.resolve(__dirname, "..");
export const PROJECT_ROOT = path.resolve(BACKEND_ROOT, "..");
export const ML_MODEL_DIR = path.resolve(PROJECT_ROOT, "ml-model");
export const DATA_DIR = path.resolve(ML_MODEL_DIR, "src", "data");
export const OUTPUT_DIR = path.resolve(PROJECT_ROOT, "output", "api-runs");

export const CONFIG = {
  port: Number.parseInt(process.env.PORT || "3000", 10),
  host: process.env.HOST || "127.0.0.1",
  corsOrigin: process.env.CORS_ORIGIN || "http://localhost:5173",
  pythonExecutable: process.env.PYTHON_EXECUTABLE || (process.platform === "win32" ? "python" : "python3"),
  runsDir: OUTPUT_DIR,
  dataDir: DATA_DIR,
  mlModelDir: ML_MODEL_DIR,
  aws: {
    region: process.env.AWS_REGION || "ap-south-1",
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || "",
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || "",
    s3BucketName: process.env.AWS_S3_BUCKET_NAME || "",
    bedrockModelId: process.env.AWS_BEDROCK_MODEL_ID || "anthropic.claude-3-haiku-20240307-v1:0",
  },
};
