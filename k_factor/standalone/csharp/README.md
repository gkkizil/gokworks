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

- `inspect` reads available sheet-metal definitions. No gauge-table query is
  required for discovery, inspection or assignment.
- `verify` writes the matched K/R values, rebuilds, reads them again, then restores
  and checks the complete original active bend-allowance payload and radius.
  A reported `verified` requires both target and restoration checks to pass.
- `apply` leaves the verified K/R values in the active configuration, unsaved.
  This is the desktop's normal assignment mode; successful edits are not restored.
- No gauge/bend table is evaluated or used to choose K/R. Material and table
  links, thickness and child overrides are not modified. If another control
  rejects or overwrites a requested parameter, rebuild/readback fails the
  assignment and triggers restoration.
- No mode saves files. A failed restoration is reported explicitly; do not save
  such a document.

K writes use `GetCustomBendAllowance`, the active payload followed by `Type`,
`SetCustomBendAllowance`, and `ModifyDefinition`. Radius writes use the documented
`ISheetMetalFeatureData.BendRadius` setter directly, in metres, followed by a
rebuild and fresh readback. No display-dimension discovery or dimension write
is involved. `radius_method` is `bend_radius_definition`.

`--self-test` validates pure parsing, matching, and report serialization without
connecting to SolidWorks. A successful build or self-test is **not** a native
SolidWorks verification.

Exit status: `0` for `inspected`, `verified`, `applied`, or `skipped`; `2` for
errors. Both stdout and the requested report file contain UTF-8 JSON.
