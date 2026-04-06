// server.js — Express Credit Card Compliance Checker Agent
require("dotenv").config();
const express = require("express");
const multer = require("multer");
const cors = require("cors");
const path = require("path");
const fs = require("fs");

const checkRoutes = require("./routes/check");
const docxRoutes = require("./routes/docx");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ extended: true }));

// Routes
app.use("/check", checkRoutes);
app.use("/docx", docxRoutes);

// Root
app.get("/", (req, res) => {
  res.json({
    name: "Credit Card Compliance Checker Agent",
    version: "1.0.0",
    endpoints: {
      "POST /check/text":       "Check plain text",
      "POST /check/file":       "Upload file (PDF, DOCX, TXT, image)",
      "POST /check/image":      "Upload image (OCR + compliance)",
      "GET  /check/regulations":"List available regulations",
      "POST /docx/generate":    "Generate color-coded DOCX from findings JSON",
      "POST /check/export":     "Check file and return DOCX in one call",
    },
  });
});

// Health check
app.get("/health", (req, res) => res.json({ status: "ok" }));

app.listen(PORT, () => {
  console.log(`Compliance Checker Agent running at http://localhost:${PORT}`);
  console.log(`API docs: http://localhost:${PORT}/`);
});
