# PowerShell script to update fields and verify Project_Documentation_Final.docx
$docxPath = "d:\New folder (2)\Project_Documentation_Final.docx"
$docsCopyPath = "d:\New folder (2)\docs\Project_Documentation_Final.docx"

Write-Host "Starting Word Application..."
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = [Microsoft.Office.Interop.Word.WdAlertLevel]::wdAlertsNone

try {
    Write-Host "Opening document: $docxPath"
    $doc = $word.Documents.Open($docxPath, [Type]::Missing, $false)

    Write-Host "Updating document fields..."
    $doc.Fields.Update()

    Write-Host "Updating Tables of Contents..."
    foreach ($toc in $doc.TablesOfContents) {
        $toc.Update()
    }

    Write-Host "Updating Tables of Figures / Tables..."
    foreach ($tof in $doc.TablesOfFigures) {
        $tof.Update()
    }

    Write-Host "Updating headers and footers across all sections..."
    foreach ($section in $doc.Sections) {
        foreach ($header in $section.Headers) {
            foreach ($field in $header.Range.Fields) {
                $field.Update()
            }
        }
        foreach ($footer in $section.Footers) {
            foreach ($field in $footer.Range.Fields) {
                $field.Update()
            }
        }
    }

    Write-Host "Saving document..."
    $doc.Save()

    # Compute Statistics
    $pages = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticPages)
    $words = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticWords)
    $characters = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticCharacters)
    $paragraphs = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticParagraphs)

    Write-Host "=================================================="
    Write-Host " FINAL DOCUMENT VERIFICATION REPORT"
    Write-Host "=================================================="
    Write-Host "Document Path    : $docxPath"
    Write-Host "Total Pages      : $pages"
    Write-Host "Total Words      : $words"
    Write-Host "Total Characters : $characters"
    Write-Host "Total Paragraphs : $paragraphs"
    Write-Host "Total Sections   : $($doc.Sections.Count)"
    Write-Host "Total Tables     : $($doc.Tables.Count)"
    Write-Host "Total Shapes/Pics: $($doc.InlineShapes.Count)"
    Write-Host "Total TOCs       : $($doc.TablesOfContents.Count)"
    Write-Host "Total TOFs       : $($doc.TablesOfFigures.Count)"
    
    for ($i = 1; $i -le $doc.Sections.Count; $i++) {
        $sec = $doc.Sections.Item($i)
        $tm = [math]::Round($sec.PageSetup.TopMargin / 72 * 25.4, 1)
        $bm = [math]::Round($sec.PageSetup.BottomMargin / 72 * 25.4, 1)
        $lm = [math]::Round($sec.PageSetup.LeftMargin / 72 * 25.4, 1)
        $rm = [math]::Round($sec.PageSetup.RightMargin / 72 * 25.4, 1)
        Write-Host "Section $i Margins: Top=${tm}mm, Bottom=${bm}mm, Left=${lm}mm, Right=${rm}mm"
    }

    if ($doc.TablesOfContents.Count -gt 0) {
        Write-Host "--- TABLE OF CONTENTS (First 15 lines) ---"
        $tocLines = ($doc.TablesOfContents.Item(1).Range.Text -split "`r`n|`r|`n")
        Write-Host "TOC Line Entries : $($tocLines.Length)"
        for ($k = 0; $k -lt [math]::Min(15, $tocLines.Length); $k++) {
            if ($tocLines[$k].Trim().Length -gt 0) {
                Write-Host "  $($tocLines[$k].Trim())"
            }
        }
    }

    if ($doc.TablesOfFigures.Count -ge 1) {
        Write-Host "--- LIST OF FIGURES ---"
        Write-Host $doc.TablesOfFigures.Item(1).Range.Text.Trim()
    }

    if ($doc.TablesOfFigures.Count -ge 2) {
        Write-Host "--- LIST OF TABLES ---"
        Write-Host $doc.TablesOfFigures.Item(2).Range.Text.Trim()
    }
    Write-Host "=================================================="
}
catch {
    Write-Error "Verification error: $_"
}
finally {
    if ($doc) {
        $doc.Close([Microsoft.Office.Interop.Word.WdSaveOptions]::wdSaveChanges)
    }
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}

# Update the docs copy as well
Copy-Item $docxPath $docsCopyPath -Force
Write-Host "Updated copy in docs folder: $docsCopyPath"
