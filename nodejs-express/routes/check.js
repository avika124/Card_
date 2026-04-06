// routes/check.js
const express = require("express");
const multer = require("multer");
const path = require("path");
const os = require("os");
const fs = require("fs");
const { checkText, checkImage, checkFile, REGULATIONS } = require("../lib/compliance");

const router = express.Router();
const upload = multer({ dest: os.tmpdir() });

router.get("/regulations", (req, res) => res.json({ regulations: REGULATIONS }));

// POST /check/text
router.post("/text", async (req, res) => {
  try {
    const { text, regulations } = req.body;
    if (!text?.trim()) return res.status(400).json({ error: "text is required" });
    const regIds = Array.isArray(regulations) ? regulations : (regulations || "").split(",").map(r => r.trim()).filter(Boolean);
    if (!regIds.length) return res.status(400).json({ error: "at least one regulation required" });
    const result = await checkText(text, regIds);
    res.json(result);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// POST /check/file
router.post("/file", upload.single("file"), async (req, res) => {
  const tmpPath = req.file?.path;
  try {
    if (!req.file) return res.status(400).json({ error: "file is required" });
    const regIds = (req.body.regulations || "").split(",").map(r => r.trim()).filter(Boolean);
    if (!regIds.length) return res.status(400).json({ error: "at least one regulation required" });

    // Rename to correct extension so pandoc/pdftotext work
    const ext = path.extname(req.file.originalname).toLowerCase();
    const renamedPath = tmpPath + ext;
    fs.renameSync(tmpPath, renamedPath);

    const result = await checkFile(renamedPath, regIds);
    fs.unlinkSync(renamedPath);
    res.json(result);
  } catch (e) {
    if (tmpPath && fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
    res.status(500).json({ error: e.message });
  }
});

// POST /check/image
router.post("/image", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: "file is required" });
    const regIds = (req.body.regulations || "").split(",").map(r => r.trim()).filter(Boolean);
    const imageBuffer = fs.readFileSync(req.file.path);
    fs.unlinkSync(req.file.path);
    const result = await checkImage(imageBuffer, req.file.mimetype, regIds);
    res.json(result);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// POST /check/export — check file and return DOCX
router.post("/export", upload.single("file"), async (req, res) => {
  const tmpPath = req.file?.path;
  try {
    if (!req.file) return res.status(400).json({ error: "file is required" });
    const regIds = (req.body.regulations || "").split(",").map(r => r.trim()).filter(Boolean);
    const ext = path.extname(req.file.originalname).toLowerCase();
    const renamedPath = tmpPath + ext;
    fs.renameSync(tmpPath, renamedPath);

    const result = await checkFile(renamedPath, regIds);
    fs.unlinkSync(renamedPath);

    // Forward to docx generator
    const { generateComplianceDocx } = require("../lib/docxGenerator");
    const docxBuffer = await generateComplianceDocx(result, req.file.originalname);

    res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    res.setHeader("Content-Disposition", 'attachment; filename="compliance_report.docx"');
    res.send(docxBuffer);
  } catch (e) {
    if (tmpPath && fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
    res.status(500).json({ error: e.message });
  }
});

module.exports = router;
