# M4 local operations

Use project Python3.12 (`.venv/bin/python`); bare systemPython3.9 lacks tomllib. Node22 PATH=/opt/homebrew/opt/node@22/bin. Default health never contacts ALM/model/vector; live flags remain false.

Sourceprofile+projectselection → sourcepreflight → processingpolicy+verifiedmodelprofile → pipeline-preflight → SYNC. Independent COLLECT/PROCESS/EMBED/INDEX are supported; INDEX requires ready compatible artifacts. Changed chunk/model/keywordmetadata version requires REBUILD_INDEX and complete coverage; failedrebuild preserves oldgeneration. Never bypass calibration/verifiedruntimeguards or download realweights automatically.

Search requires explicit authorizedproject_uids and searchpermission. Exactsource/internalID is case-preserving withinprojectscope, including zeroChunkpublications. Optional filters OR within identitylists/AND acrossfields; finite typedJSONequality, missing!=null,bool!=number. Filter metadata describes publishedrevision, while currentselection still governsvisibility. Too-broadfilter>10000eligibleItems/project explicitlyfails, never silentlytruncates.

GET jobs/{id}/failed-items requiresproject_read. Single/bulk retry andresume requireproject_manage, pinnedrevision/config guards and durableFIFO. Default replay startsfailedstage; force_recollectexplicitlycallsconfiguredreadonlysource. SourceIDs arenotfilesystempaths/URLs. Errors sanitized; do notputsecret/rawsourceinto logs.

Worker schedules retiredgenerationcleanup outside jobheartbeat; alive OSreaderlocks blockcleanup. Originalrevisions retained; removedderivedindex isnotpermanentrollback. Keepdatabase+readerlocks on tested localfilesystem; distributed/sharedlocksemanticsnotverified.

Validation: projectpytest; actualQdrantonlywith ALMRAG_TEST_QDRANT_URL=http://127.0.0.1:16333 against dedicatedsyntheticcontainer, not configuredproductionURL. Build localimages and tools/smoke_m4.py via --network none. Currentrealmodel/ALM/remoteCI remainNV. Never use syntheticfixtureprofiles as productionverification.
