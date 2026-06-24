/**
 * Baskerville Book Template Creator
 *
 * Creates an InDesign master document configured for:
 *   - Sheet:    12" × 9" physical paper, printed as a booklet
 *   - Page:     6" × 9" per InDesign page (facing pages)
 *   - Bleed:    0.125" (3.1 mm) on all four sides
 *   - Margins:  Top 0.75" | Bottom 0.75" | Outside 0.75" | Inside (binding) 1"
 *   - Font:     Baskerville 12 pt body, 11 pt page numbers
 *   - Numbers:  Bottom-center on every page via master-page auto-number frame
 *
 * Signatures: every 8 pages form one saddle-stitched signature.
 *   Outer sheet → pages 1, 2, 7, 8
 *   Inner sheet → pages 3, 4, 5, 6
 * Print via File > Print Booklet > 2-Up Saddle Stitch to get correct imposition.
 *
 * HOW TO RUN:
 *   In InDesign: Window > Utilities > Scripts, navigate to this file, double-click.
 *   The resulting template is saved to your Desktop as Baskerville_Template.indt
 */

#target indesign

(function () {
    "use strict";

    // ── Document ──────────────────────────────────────────────────────────────
    var doc = app.documents.add(true);
    var dp  = doc.documentPreferences;

    dp.facingPages      = true;
    dp.pageWidth        = "6in";    // each leaf = half the 12"×9" sheet
    dp.pageHeight       = "9in";
    dp.pagesPerDocument = 8;        // one full signature to start

    // Bleed 0.125" on every side
    dp.documentBleedTopOffset            = "0.125in";
    dp.documentBleedBottomOffset         = "0.125in";
    dp.documentBleedInsideOrLeftOffset   = "0.125in";
    dp.documentBleedOutsideOrRightOffset = "0.125in";

    // ── Master Page Margins ───────────────────────────────────────────────────
    // masterSpreads[0].pages[0] = verso (left / even pages)
    // masterSpreads[0].pages[1] = recto (right / odd pages)
    var ms          = doc.masterSpreads[0];
    var versoMaster = ms.pages[0];
    var rectoMaster = ms.pages[1];

    // Verso: spine is on the RIGHT side of this page
    var vm = versoMaster.marginPreferences;
    vm.top    = "0.75in";
    vm.bottom = "0.75in";
    vm.left   = "0.75in";   // outside edge
    vm.right  = "1in";      // inside / binding edge

    // Recto: spine is on the LEFT side of this page
    var rmp = rectoMaster.marginPreferences;
    rmp.top    = "0.75in";
    rmp.bottom = "0.75in";
    rmp.left   = "1in";     // inside / binding edge
    rmp.right  = "0.75in";  // outside edge

    // ── Font Helper ───────────────────────────────────────────────────────────
    // InDesign accepts "Family\tStyle" strings for appliedFont.
    function applyBaskerville(style, ptSize) {
        var attempts = [
            "Baskerville\tRegular",
            "Baskerville Regular",
            "Baskerville"
        ];
        for (var i = 0; i < attempts.length; i++) {
            try {
                style.appliedFont = attempts[i];
                break;
            } catch (e) { /* try next */ }
        }
        style.pointSize = ptSize;
    }

    // ── Paragraph Styles ──────────────────────────────────────────────────────
    var bodyStyle = doc.paragraphStyles.add();
    bodyStyle.name = "Body Text";
    applyBaskerville(bodyStyle, 12);
    bodyStyle.leading      = 15;                       // 15 pt leading for 12 pt body
    bodyStyle.justification = Justification.LEFT_ALIGN;

    var pageNumStyle = doc.paragraphStyles.add();
    pageNumStyle.name = "Page Number";
    applyBaskerville(pageNumStyle, 11);
    pageNumStyle.justification = Justification.CENTER_ALIGN;

    // ── Auto-Number Frames on Master Pages ───────────────────────────────────
    // IMPORTANT — Master spreads use SPREAD-relative coordinates, not page-
    // relative. Both pages live in a single spread whose x-axis runs from 0
    // (left edge of the verso page) to 12" (right edge of the recto page).
    // Any frame with x coordinates inside 0–6" lands on the left (verso) page;
    // frames intended for the right (recto) page must have x coordinates > 6".
    // Calling .add() on the recto page object but supplying x < 6" silently
    // places the frame on the verso page — this was the source of "odd pages
    // have no page number" in InDesign 2026.
    var PAGE_W = 6; // inches, must match dp.pageWidth

    function addPageNumberFrame(page, xOff) {
        var f = page.textFrames.add();
        // Bottom-margin zone: y 8.35"–8.65", horizontally centred on the page.
        // xOff shifts the frame into the correct half of the spread.
        f.geometricBounds = [
            "8.35in",
            (1.75 + xOff) + "in",
            "8.65in",
            (4.25 + xOff) + "in"
        ];
        f.insertionPoints.item(0).contents = SpecialCharacters.AUTO_PAGE_NUMBER;
        f.paragraphs.item(0).appliedParagraphStyle = pageNumStyle;
        return f;
    }

    addPageNumberFrame(versoMaster, 0);       // left half: x unchanged
    addPageNumberFrame(rectoMaster, PAGE_W);  // right half: x offset by 6"

    // ── Primary Text Frames on Master Pages ──────────────────────────────────
    // Verso text area (left half of spread, x = 0–6"):
    //   x1 = outside margin = 0.75"
    //   x2 = 6" − 1" (inside) = 5.0"
    var versoTF = versoMaster.textFrames.add();
    versoTF.geometricBounds = ["0.75in", "0.75in", "8.25in", "5.0in"];
    versoTF.label = "Primary Text Frame";

    // Recto text area (right half of spread, x = 6"–12"):
    //   x1 = 6" + 1.0" (inside) = 7.0"
    //   x2 = 6" + 5.25" (outside) = 11.25"
    var rectoTF = rectoMaster.textFrames.add();
    rectoTF.geometricBounds = ["0.75in", "7.0in", "8.25in", "11.25in"];
    rectoTF.label = "Primary Text Frame";

    // Thread the two master frames so text can flow verso → recto
    versoTF.nextTextFrame = rectoTF;

    // ── Save as Template ──────────────────────────────────────────────────────
    var saveFile = new File(Folder.desktop + "/Baskerville_Template.indt");
    doc.save(saveFile);

    alert(
        "Template saved to Desktop:\n  Baskerville_Template.indt\n\n" +
        "Specs confirmed:\n" +
        "  Page size : 6\" × 9\" (half of 12\"×9\" sheet)\n" +
        "  Facing    : Yes\n" +
        "  Margins   : T/B/Outside 0.75\" · Inside 1\"\n" +
        "  Bleed     : 0.125\" all sides\n" +
        "  Body font : Baskerville 12 pt / 15 pt leading\n" +
        "  Page nums : Baskerville 11 pt, bottom center\n\n" +
        "Use the Typesetter app (typesetter_app.py) to import text into this layout."
    );
})();
