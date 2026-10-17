# Typed SolidWorks K/R assignment engine

This is the native engine used by the standalone K/R assignment desktop,
independent of GOKWORKS's production assembly K/R writer.
It uses the installed, strongly typed SolidWorks COM interfaces, without C#
`dynamic`, reflection dispatch, or a new SolidWorks process.

Requirements: 64-bit Windows, .NET 8 SDK, and a running SolidWorks instance.
Activate one **saved `.SLDPRT` in its own window**, in the configuration you want
to examine. This probe does not traverse an assembly or claim to update every
bend. Child definitions are listed as metadata; their overrides are not reset.

Build from this directory:

```powershell
dotnet build Gokworks.KrProbe.csproj -c Release `
  "-p:SolidWorksInteropDir=C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist"
```

`SolidWorksInteropDir` must contain the installed
`SolidWorks.Interop.sldworks.dll` and `SolidWorks.Interop.swconst.dll`.
They are references, not source files to commit to this repository.

Run with the same JSON request used by the independent Python implementation:

```powershell
dotnet .\bin\Release\net8.0-windows\Gokworks.KrProbe.dll `
  --request ..\examples\inspect.json --report .\inspect-report.json
```

See the [shared instructions](../README.md) for the request schema and sequential
native desktop workflow. C#/Python comparison is an optional developer diagnostic.

- `inspect` reads available sheet-metal definitions. Gauge-table status code `2`
  is recorded as `NotEnabledOnTemplate`, rather than incorrectly interpreted as
  `false` or used to abort feature discovery.
- `verify` writes the matched K/R values, rebuilds, reads them again, then restores
  and checks the complete original active bend-allowance payload and radius.
  A reported `verified` requires both target and restoration checks to pass.
- `apply` leaves the verified K/R values in the active configuration, unsaved.
  This is the desktop's normal assignment mode; successful edits are not restored.
- Gauge getter status `2` is supported only on `TemplateSheetMetal`, status `1`
  only on legacy `SheetMetal`. They are reported as unavailable getter results,
  not interpreted as false OUT values. Known gauge/material links or genuine
  errors block writes; no control or child override is disabled.
- No mode saves files. A failed restoration is reported explicitly; do not save
  such a document.

K writes use `GetCustomBendAllowance`, the active payload followed by `Type`,
`SetCustomBendAllowance`, and `ModifyDefinition`. Radius writes prefer exactly one
radial display dimension owned by the selected definition, using
`SetSystemValue3` for the current configuration. With no owned radial dimension,
the probe tests the documented `BendRadius` setter and requires a successful
readback. `radius_method` records the route used. Diameter dimensions and
dimensions belonging to subfeatures are never used as radius targets.

`--self-test` validates pure parsing, matching, and report serialization without
connecting to SolidWorks. A successful build or self-test is **not** a native
SolidWorks verification.

Exit status: `0` for `inspected`, `verified`, `applied`, or `skipped`; `2` for
errors. Both stdout and the requested report file contain UTF-8 JSON.
