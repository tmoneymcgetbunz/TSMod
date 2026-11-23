-- [TSMod] Shop unlock repair (2026-11-23). The story switches shops on with EnableReleaseFunction at fixed story points
-- (Progress/TriggerAnchorEvent, ShopFlagList). A save moved past those points by the save editor's story jump never ran
-- them, so its camp has no smithy, tavern or sundry shop (slot 5, user 2026-11-23). On load, switch on every shop whose
-- story point the save has passed, with the shipped conditions. Saves from normal play already have them: no change.
local function tsmod_ur_log(...)
  if TSLOG ~= nil then pcall(TSLOG, "unlock_repair", ...) end
end
local function tsmod_unlock_repair()
  local ok, err = pcall(function()
    local a = GetSysGlobal(SysGlobal.SCENARIO_ANCHOR)
    if type(a) ~= "number" then return end
    local rules = {
      {EFunctionFlagSHOP_ITEM, EScenarioAnchorSA_MS02_X02_HD010, "item"},
      {EFunctionFlagSHOP_SMITH, EScenarioAnchorSA_MS02_X02_RS010, "smith"},
      {EFunctionFlagSHOP_BAR, EScenarioAnchorSA_MS03_H01_HD010, "bar"},
      {EFunctionFlagSHOP_GENERAL, EScenarioAnchorSA_MS03_H01_VT010, "general"},
    }
    local okc, cnt = pcall(GetSysGlobal, SysGlobal.GAME_RESULT_COUNT)
    if okc and type(cnt) == "number" and cnt > 0 then
      rules[#rules + 1] = {EFunctionFlagSHOP_GENERAL_SCOUT, EScenarioAnchorSA_MS05_X06_HD010, "scout"}
    end
    for _, r in ipairs(rules) do
      if r[1] ~= nil and r[2] ~= nil and a >= r[2] and IsReleaseFunction(r[1]) ~= true then
        EnableReleaseFunction(r[1])
        tsmod_ur_log("enabled", r[3], "anchor", a)
      end
    end
  end)
  if not ok then tsmod_ur_log("Lua error", err) end
end
local tsmod_ur_orig_postinit = ClassWorldMapImplementation.OnPostInitialize_Implementation
function ClassWorldMapImplementation:OnPostInitialize_Implementation()
  tsmod_unlock_repair()
  return tsmod_ur_orig_postinit(self)
end
