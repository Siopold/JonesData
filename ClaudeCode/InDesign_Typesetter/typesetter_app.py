"""
Baskerville Typesetter
======================
Drag-and-drop (or browse) a .txt, .docx, .doc, or .rtf file.
Click "Create InDesign File" and InDesign opens a fully typeset document.

Document specs baked in:
  Page      6" × 9" (half of 12"×9" physical sheet), facing pages
  Margins   Top/Bottom/Outside 0.75" · Inside/binding 1"
  Bleed     0.125" all sides
  Body      Baskerville 12 pt, 15 pt leading
  Numbers   Baskerville 11 pt, bottom center, auto-numbered

Requires: macOS + Adobe InDesign (any recent CC version)
Run with: python3 typesetter_app.py
"""

import os
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

# ── Embedded InDesign Script ──────────────────────────────────────────────────
# INPUT_FILE_PATH is prepended by Python before execution.

INDESIGN_SCRIPT_BODY = r"""
(function () {
    "use strict";

    // INPUT_FILE_PATH is injected by typesetter_app.py
    var textFile = new File(INPUT_FILE_PATH);
    if (!textFile.exists) {
        alert("File not found:\n" + INPUT_FILE_PATH);
        return;
    }

    // ── Document ──────────────────────────────────────────────────────────
    var doc = app.documents.add(true);
    var dp  = doc.documentPreferences;

    dp.facingPages      = true;
    dp.pageWidth        = "6in";
    dp.pageHeight       = "9in";
    // Start with ONE page (page 1, recto). We add pages one-by-one below so
    // we always know exactly which page number each new frame lands on.
    // Starting with 2 pages would leave page 2 with no text frame and cause
    // all subsequent text to pile up on wrong pages.
    dp.pagesPerDocument = 1;

    dp.documentBleedTopOffset            = "0.125in";
    dp.documentBleedBottomOffset         = "0.125in";
    dp.documentBleedInsideOrLeftOffset   = "0.125in";
    dp.documentBleedOutsideOrRightOffset = "0.125in";

    // ── Master Page Margins ───────────────────────────────────────────────
    // The A-Master of a facing-pages document always has exactly two pages:
    //   item(0) = left / verso  (even page numbers, spine on right)
    //   item(1) = right / recto (odd page numbers,  spine on left)
    // Direct indexing avoids the side-detection loop that caused item(0) to
    // receive two page-number frames and item(1) to receive none.
    var ms          = doc.masterSpreads[0];
    var versoMaster = ms.pages.item(0);
    var rectoMaster = ms.pages.item(1);

    // Verso: spine is on the RIGHT → left=outside(0.75"), right=inside(1")
    var vm = versoMaster.marginPreferences;
    vm.top = "0.75in"; vm.bottom = "0.75in";
    vm.left = "0.75in"; vm.right = "1in";

    // Recto: spine is on the LEFT → left=inside(1"), right=outside(0.75")
    var rm = rectoMaster.marginPreferences;
    rm.top = "0.75in"; rm.bottom = "0.75in";
    rm.left = "1in"; rm.right = "0.75in";

    // ── Font Helper ───────────────────────────────────────────────────────
    function applyBaskerville(style, ptSize) {
        var names = ["Baskerville\tRegular", "Baskerville Regular", "Baskerville"];
        for (var i = 0; i < names.length; i++) {
            try { style.appliedFont = names[i]; break; } catch (e) {}
        }
        style.pointSize = ptSize;
    }

    // ── Paragraph Styles ─────────────────────────────────────────────────
    var bodyStyle = doc.paragraphStyles.add();
    bodyStyle.name = "Body Text";
    applyBaskerville(bodyStyle, 12);
    bodyStyle.leading      = 15;
    bodyStyle.justification = Justification.LEFT_ALIGN;
    bodyStyle.spaceAfter   = 6;   // 6pt gap between prose paragraphs

    // Poetry lines are kept as individual InDesign paragraphs (line breaks
    // preserved) with no extra space between them. The LAST line of each
    // poetry block uses bodyStyle instead so there's a gap before the
    // next paragraph.
    var poetryStyle = doc.paragraphStyles.add();
    poetryStyle.name = "Poetry";
    applyBaskerville(poetryStyle, 12);
    poetryStyle.leading      = 15;
    poetryStyle.justification = Justification.LEFT_ALIGN;
    poetryStyle.spaceAfter   = 0;

    var pageNumStyle = doc.paragraphStyles.add();
    pageNumStyle.name = "Page Number";
    applyBaskerville(pageNumStyle, 11);
    pageNumStyle.justification = Justification.CENTER_ALIGN;

    // ── Auto-Number Frames on Both Master Pages ───────────────────────────
    // Master spreads use SPREAD-relative coordinates, not page-relative.
    // The left (verso) page occupies x = 0…6"; the right (recto) page occupies
    // x = 6"…12". Any frame whose x coordinates fall in 0–6" lands on the left
    // page regardless of which page object received the add() call. Frames
    // intended for the recto page must therefore have x coordinates shifted
    // right by one page width (6 inches).
    var PAGE_W = 6; // inches — must match dp.pageWidth above

    function addPageNumberFrame(page, xOff) {
        var f = page.textFrames.add();
        // y: 8.35"–8.65" (bottom-margin zone); x: centred on the page,
        // then shifted by xOff so it lands in the correct half of the spread.
        f.geometricBounds = [
            "8.35in",
            (1.75 + xOff) + "in",
            "8.65in",
            (4.25 + xOff) + "in"
        ];
        f.insertionPoints.item(0).contents = SpecialCharacters.AUTO_PAGE_NUMBER;
        f.paragraphs.item(0).appliedParagraphStyle = pageNumStyle;
    }
    addPageNumberFrame(versoMaster, 0);       // left page: no x offset
    addPageNumberFrame(rectoMaster, PAGE_W);  // right page: shift x by 6"

    // ── Text Frame Bounds by Page Number ─────────────────────────────────
    // Facing-pages documents use SPREAD-relative coordinates for all page
    // items — the same rule that applies to master pages.
    //
    // Page 1 (recto) is alone in spread 1: the spread is only 6" wide, so
    // x = 0–6" covers the whole page and no offset is needed.
    //
    // Pages 2+ live in two-page spreads (12" wide):
    //   Even pages (verso) = left half,  x = 0–6"   → no offset
    //   Odd pages  (recto) = right half, x = 6–12"  → +6" x offset
    //
    // Without the offset, recto frames (pages 3, 5, 7 …) land in the left
    // half of their spread and stack on top of the preceding verso frame.
    function boundsForPageNum(n) {
        var xOff = (n % 2 === 1 && n > 1) ? 6 : 0;
        return (n % 2 === 0)
            ? ["0.75in", (0.75 + xOff) + "in", "8.25in", (5.0  + xOff) + "in"]  // verso
            : ["0.75in", (1.0  + xOff) + "in", "8.25in", (5.25 + xOff) + "in"]; // recto
    }

    // ── Place Text and Auto-flow ──────────────────────────────────────────
    // Page 1 (recto) already exists; create its text frame directly.
    var firstPage  = doc.pages.item(0);
    var firstFrame = firstPage.textFrames.add();
    firstFrame.geometricBounds = boundsForPageNum(1);

    // InDesign's frame.place() defaults to Mac Roman for .txt files, which
    // corrupts em-dashes and other non-ASCII characters (e.g. U+2014 becomes
    // ‚Äî). TextFileCharacterSet was removed in InDesign 2026. Instead, read
    // the file via ExtendScript's File API (which honours .encoding = "UTF-8")
    // and set the frame contents directly. DOCX/RTF carry their own encoding
    // metadata, so they still go through place().
    var ext = textFile.name.toLowerCase().replace(/.*\./, "");
    if (ext === "txt") {
        textFile.encoding = "UTF-8";
        textFile.open("r");
        var rawText = textFile.read();
        textFile.close();

        // Normalise line endings, then split on blank lines to find real
        // paragraph / stanza boundaries.
        rawText = rawText.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        var sections = rawText.split(/\n{2,}/);

        // For each blank-line-separated block decide whether it is:
        //   prose  — no line starts with whitespace → join soft-wraps into
        //            one InDesign paragraph (bodyStyle, spaceAfter=6pt)
        //   poetry — at least one line starts with a space or tab → keep
        //            every line as its own InDesign paragraph (poetryStyle,
        //            spaceAfter=0), except the last line of the block which
        //            uses bodyStyle so there is a gap before the next block.
        var contentParts = [];  // one entry per InDesign paragraph
        var paraStyles   = [];  // parallel: which style to apply

        for (var si = 0; si < sections.length; si++) {
            var section = sections[si].replace(/^\s+/, "").replace(/\s+$/, "");
            if (!section) continue;

            var lines = section.split("\n");

            var isPoetry = false;
            for (var li = 0; li < lines.length; li++) {
                if (/^[ \t]/.test(lines[li])) { isPoetry = true; break; }
            }

            if (isPoetry) {
                var plines = [];
                for (var pi = 0; pi < lines.length; pi++) {
                    var ln = lines[pi].replace(/\s+$/, "");
                    if (ln.replace(/\s/g, "").length > 0) plines.push(ln);
                }
                for (var qi = 0; qi < plines.length; qi++) {
                    contentParts.push(plines[qi]);
                    // Last line of a poetry block → bodyStyle (provides the
                    // gap before the next paragraph); all others → poetryStyle.
                    paraStyles.push(qi === plines.length - 1 ? bodyStyle : poetryStyle);
                }
            } else {
                var prose = section.replace(/\n/g, " ").replace(/  +/g, " ");
                prose = prose.replace(/^\s+/, "").replace(/\s+$/, "");
                if (prose.length > 0) {
                    contentParts.push(prose);
                    paraStyles.push(bodyStyle);
                }
            }
        }

        firstFrame.contents = contentParts.join("\r");

        // Apply per-paragraph styles (replaces the blanket everyItem() call).
        var story = firstFrame.parentStory;
        for (var xi = 0; xi < paraStyles.length && xi < story.paragraphs.length; xi++) {
            story.paragraphs[xi].appliedParagraphStyle = paraStyles[xi];
        }
    } else {
        firstFrame.place(textFile);
        firstFrame.parentStory.paragraphs.everyItem().appliedParagraphStyle = bodyStyle;
    }

    var frame   = firstFrame;
    var pageNum = 1;    // tracks which page number the current frame is on
    var safety  = 0;

    while (frame.overflows && safety < 2000) {
        pageNum++;
        doc.pages.add(LocationOptions.AT_END);
        // Use explicit length-based index — more reliable than doc.pages[-1]
        // across InDesign versions.
        var np = doc.pages.item(doc.pages.length - 1);
        var nf = np.textFrames.add();
        nf.geometricBounds = boundsForPageNum(pageNum);
        frame.nextTextFrame = nf;
        frame = nf;
        safety++;
    }

    // Pad to complete 8-page signatures
    var sigs   = Math.ceil(doc.pages.length / 8);
    var target = sigs * 8;
    while (doc.pages.length < target) {
        doc.pages.add(LocationOptions.AT_END);
    }

    alert(
        "Import complete!\n\n" +
        doc.pages.length + " pages  ·  " + sigs +
        " signature" + (sigs !== 1 ? "s" : "") + "\n\n" +
        "Pages are in reading order (1, 2, 3…).\n" +
        "To impose and print as a saddle-stitched booklet:\n\n" +
        "  File → Print Booklet → 2-Up Saddle Stitch\n\n" +
        "InDesign will automatically arrange each 8-page\n" +
        "signature so the outer sheet carries pp. 1-2 & 7-8\n" +
        "and the inner sheet carries pp. 3-4 & 5-6."
    );
})();
"""


# ── Python GUI ────────────────────────────────────────────────────────────────

ACCENT   = "#2c3e50"
BTN_BLUE = "#2980b9"
BTN_GRN  = "#27ae60"
BTN_DIS  = "#95a5a6"
BG       = "#f5f5f0"


class TypesetterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Baskerville Typesetter")
        self.root.geometry("520x430")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self._file_path: str = ""
        self._build_ui()
        self._try_enable_dnd()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Header bar
        header = tk.Frame(self.root, bg=ACCENT, height=56)
        header.pack(fill=tk.X)
        tk.Label(
            header, text="Baskerville Typesetter",
            font=("Georgia", 17, "bold"), fg="white", bg=ACCENT
        ).pack(pady=14)

        # Main content
        body = tk.Frame(self.root, bg=BG, padx=24, pady=18)
        body.pack(fill=tk.BOTH, expand=True)

        # Drop / select zone
        zone_frame = tk.LabelFrame(
            body, text="  Document  ", font=("Helvetica", 10),
            bg=BG, padx=10, pady=10
        )
        zone_frame.pack(fill=tk.X, pady=(0, 14))

        self.drop_label = tk.Label(
            zone_frame,
            text="Drag a file here  –or–  click Browse",
            font=("Helvetica", 10), fg="#888", bg="#eae8e0",
            relief=tk.FLAT, bd=0, pady=22, padx=10,
            cursor="hand2"
        )
        self.drop_label.pack(fill=tk.X)
        self.drop_label.bind("<Button-1>", lambda _e: self._browse())

        browse_btn = tk.Button(
            zone_frame, text="Browse…",
            font=("Helvetica", 10), bg=BTN_BLUE, fg="white",
            relief=tk.FLAT, padx=12, pady=4,
            activebackground="#1a6fa3", activeforeground="white",
            cursor="hand2", command=self._browse
        )
        browse_btn.pack(pady=(8, 0))

        # Selected path display
        tk.Label(body, text="Selected file:", font=("Helvetica", 9),
                 fg="#555", bg=BG).pack(anchor=tk.W)
        self.path_var = tk.StringVar(value="(none)")
        tk.Label(
            body, textvariable=self.path_var,
            font=("Courier", 9), fg="#333", bg=BG,
            wraplength=468, anchor=tk.W, justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(2, 12))

        # Convert button
        self.go_btn = tk.Button(
            body, text="Create InDesign File",
            font=("Helvetica", 12, "bold"),
            bg=BTN_DIS, fg="white", relief=tk.FLAT,
            padx=16, pady=10, state=tk.DISABLED,
            activebackground="#1e8449", activeforeground="white",
            cursor="hand2", command=self._convert
        )
        self.go_btn.pack(fill=tk.X, pady=(0, 8))

        # Status
        self.status_var = tk.StringVar(value="Ready – select a .txt or .docx file.")
        tk.Label(
            body, textvariable=self.status_var,
            font=("Helvetica", 9), fg="#777", bg=BG,
            wraplength=468, justify=tk.LEFT
        ).pack(anchor=tk.W)

        # Spec summary
        tk.Label(
            body,
            text=(
                "Specs: 6\"×9\" pages · Facing · Baskerville 12 pt · "
                "Margins T/B/Out 0.75\" / In 1\" · Bleed 0.125\""
            ),
            font=("Helvetica", 8), fg="#aaa", bg=BG, justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(12, 0))

    # ── Drag-and-drop (tkinterdnd2 if available) ──────────────────────────────

    def _try_enable_dnd(self) -> None:
        try:
            from tkinterdnd2 import DND_FILES
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass  # DND unavailable; Browse button still works

    def _on_drop(self, event) -> None:
        path = event.data.strip().strip("{}")
        self._set_file(path)

    # ── File selection ────────────────────────────────────────────────────────

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a text or Word document",
            filetypes=[
                ("Supported files", "*.txt *.docx *.doc *.rtf"),
                ("Plain text",      "*.txt"),
                ("Word documents",  "*.docx *.doc"),
                ("Rich Text",       "*.rtf"),
                ("All files",       "*.*"),
            ]
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str) -> None:
        if not os.path.isfile(path):
            messagebox.showerror("Not found", f"Cannot locate:\n{path}")
            return
        self._file_path = path
        name = os.path.basename(path)
        self.path_var.set(path)
        self.drop_label.config(text=f"✓  {name}", fg="#1e8449")
        self.go_btn.config(state=tk.NORMAL, bg=BTN_GRN)
        self.status_var.set(f"Ready to typeset: {name}")

    # ── InDesign conversion ───────────────────────────────────────────────────

    def _convert(self) -> None:
        if not self._file_path:
            messagebox.showerror("No file", "Please select a file first.")
            return
        if not os.path.isfile(self._file_path):
            messagebox.showerror("Not found", f"File not found:\n{self._file_path}")
            return

        # Embed file path as a JS variable before the main script body
        jsx_path = self._file_path.replace("\\", "/").replace('"', '\\"')
        jsx_content = f'var INPUT_FILE_PATH = "{jsx_path}";\n' + INDESIGN_SCRIPT_BODY

        # Write to a temp file that InDesign will read
        tmp = tempfile.NamedTemporaryFile(suffix=".jsx", delete=False,
                                          mode="w", encoding="utf-8")
        tmp.write(jsx_content)
        tmp.close()

        self.status_var.set("Sending to InDesign…")
        self.root.update()

        try:
            self._run_in_indesign(tmp.name)
            self.status_var.set("InDesign is typesetting your document.")
        except RuntimeError as exc:
            messagebox.showerror("InDesign Error", str(exc))
            self.status_var.set("Error – see dialog for details.")

    def _run_in_indesign(self, jsx_file: str) -> None:
        """Try several AppleScript forms to launch InDesign and run the JSX."""
        # Using bundle ID avoids hardcoding the version year
        forms = [
            # Preferred: POSIX file reference
            f'tell application id "com.adobe.InDesign"\n'
            f'  activate\n'
            f'  do script POSIX file "{jsx_file}" language javascript\n'
            f'end tell',
            # Fallback: quoted string path
            f'tell application id "com.adobe.InDesign"\n'
            f'  activate\n'
            f'  do script "{jsx_file}" language javascript\n'
            f'end tell',
            # Last resort: named application (most recent InDesign)
            f'tell application "Adobe InDesign"\n'
            f'  activate\n'
            f'  do script POSIX file "{jsx_file}" language javascript\n'
            f'end tell',
        ]
        last_err = ""
        for script in forms:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return
            last_err = (result.stderr or result.stdout).strip()

        raise RuntimeError(
            "Could not communicate with Adobe InDesign.\n\n"
            "Make sure InDesign is installed and try opening it manually first.\n\n"
            f"Detail: {last_err}"
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    # Try tkinterdnd2 root for native drag-and-drop
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except Exception:
        root = tk.Tk()

    TypesetterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
