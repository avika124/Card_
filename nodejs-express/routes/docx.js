// routes/docx.js
const express = require("express");
const { generateComplianceDocx } = require("../lib/docxGenerator");

const router = express.Router();

// POST /docx/generate
router.post("/generate", async (req, res) => {
  try {
    const { findings, document_name, original_excerpt } = req.body;
    if (!findings) return res.status(400).json({ error: "findings JSON is required" });

    const findingsObj = typeof findings === "string" ? JSON.parse(findings) : findings;
    const docxBuffer = await generateComplianceDocx(
      findingsObj,
      document_name || "Analyzed Document",
      original_excerpt || ""
    );

    res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    res.setHeader("Content-Disposition", 'attachment; filename="compliance_report.docx"');
    res.send(docxBuffer);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

module.exports = router;
