# PowerShell script to inspect and verify Project_Documentation.docx properties
$docxPath = "d:\New folder (2)\docs\Project_Documentation.docx"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($docxPath, [Type]::Missing, $true)
    
    $pages = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticPages)
    $words = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticWords)
    $characters = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticCharacters)
    $paragraphs = $doc.ComputeStatistics([Microsoft.Office.Interop.Word.WdStatistic]::wdStatisticParagraphs)
    
    Write-Host "=================================================="
    Write-Host " DOCUMENT VERIFICATION REPORT"
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
        $tocRange = $doc.TablesOfContents.Item(1).Range.Text
        $tocLines = ($tocRange -split "`r`n|`r|`n").Length
        Write-Host "TOC Line Entries : $tocLines"
    }
    Write-Host "=================================================="
}
catch {
    Write-Error "Verification error: $_"
}
finally {
    if ($doc) {
        $doc.Close([Microsoft.Office.Interop.Word.WdSaveOptions]::wdDoNotSaveChanges)
    }
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
