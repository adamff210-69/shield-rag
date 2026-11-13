# PowerShell script to update TOC, List of Figures, List of Tables, and Page Numbers via Word COM
$docxPath = "d:\New folder (2)\docs\Project_Documentation.docx"

Write-Host "Opening Word application..."
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = [Microsoft.Office.Interop.Word.WdAlertLevel]::wdAlertsNone

try {
    Write-Host "Opening document: $docxPath"
    $doc = $word.Documents.Open($docxPath, [Type]::Missing, $false)

    Write-Host "Updating all document fields..."
    $doc.Fields.Update()

    Write-Host "Updating Tables of Contents..."
    foreach ($toc in $doc.TablesOfContents) {
        $toc.Update()
    }

    Write-Host "Updating Tables of Figures / Tables..."
    foreach ($tof in $doc.TablesOfFigures) {
        $tof.Update()
    }

    Write-Host "Updating header and footer fields across all sections..."
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
    Write-Host "Fields successfully updated and document saved."
}
catch {
    Write-Error "Error updating document fields: $_"
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
