-- [TSMod] deploy_fix (1/2): record each battle's deploy squares in the game's own order, for the ChangeSortieUnits
-- fix in Battle/BattlePreparation (see that file). The native square table is append-only and only accepts squares
-- during the battle's first setup (exe +d28eb0); this mirrors exactly that call. Never errors out.
if _G ~= nil and rawget(_G, "TSMOD_DEPLOY_HOOKED") == nil then
  rawset(_G, "TSMOD_DEPLOY_HOOKED", true)
  rawset(_G, "TSMOD_DEPLOY_SQUARES", {})
  rawset(_G, "TSMOD_DEPLOY_PROHIBITED", {})
  local tsmod_df_add = rawget(_G, "AddInitialPosition")
  if type(tsmod_df_add) == "function" then
    rawset(_G, "AddInitialPosition", function(x, y, ...)
      if rawget(_G, "TSMOD_DEPLOY_CAPTURE") == true then
        pcall(function()
          local sq = rawget(_G, "TSMOD_DEPLOY_SQUARES")
          sq[#sq + 1] = {x, y}
        end)
      end
      return tsmod_df_add(x, y, ...)
    end)
  end
  local tsmod_df_prohibit = rawget(_G, "AddProhibitedUnits")
  if type(tsmod_df_prohibit) == "function" then
    rawset(_G, "AddProhibitedUnits", function(units, ...)
      if rawget(_G, "TSMOD_DEPLOY_CAPTURE") == true then
        pcall(function()
          local p = rawget(_G, "TSMOD_DEPLOY_PROHIBITED")
          for _, u in ipairs(units) do p[tostring(u)] = true end
        end)
      end
      return tsmod_df_prohibit(units, ...)
    end)
  end
end

local function tsmod_df_wrap_setup(fname)
  local orig = ClassBattlePreparationBase ~= nil and ClassBattlePreparationBase[fname] or nil
  if type(orig) ~= "function" then return end
  ClassBattlePreparationBase[fname] = function(self, ...)
    local first = false
    pcall(function()
      if rawget(_G, "TSMOD_DEPLOY_OWNER") ~= self then   -- a new battle: only its first setup call fills the table
        rawset(_G, "TSMOD_DEPLOY_OWNER", self)
        rawset(_G, "TSMOD_DEPLOY_SQUARES", {})
        rawset(_G, "TSMOD_DEPLOY_PROHIBITED", {})
        rawset(_G, "TSMOD_DEPLOY_CAPTURE", true)
        first = true
      end
    end)
    -- no pcall around the original: game scripts may Wait (yield), which can't cross a pcall in Lua 5.1
    local r = {orig(self, ...)}
    if first then pcall(rawset, _G, "TSMOD_DEPLOY_CAPTURE", false) end
    return unpack(r)
  end
end
tsmod_df_wrap_setup("CreateDataOnly")
tsmod_df_wrap_setup("SetupInittialPosition_Impl")
