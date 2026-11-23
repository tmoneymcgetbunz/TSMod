-- [TSMod] Batch D (Idore). Puppet Master puts the Hierophant on Idore's side.
-- Test 38b [tested]: a player-cast Puppet Master spawns UNIT_MASTER_CH_N201_2 on team 1 (enemy), AI-controlled; her own
-- Pull Strings puppets also join team 1. No data field sets a summon's side. The native ChangeUnitFriendlyType(unit,
-- bool) [read, +ed7c80] writes unit data +0x104 (true -> 1, false -> 2) and, if the unit's team changed, moves it from
-- the old team list to the new one. Shipped only in a dev script (BattleUnitTest.lua).
-- So: units that appear during Idore's Puppet Master, or during a turn of a unit we already flipped (her Pull
-- Strings), are flipped after the action with ChangeUnitFriendlyType(u, true).
-- Test 38c [tested]: true -> team 0 (player), AI type 0: the player controls her, no issues seen. false -> no change
-- (stays team 1). Only units that really joined team 0 count as ours, so an enemy Hierophant's puppets stay hostile.
local TSMOD_D_PUPPET = "BATTLE_ABILITY_PUPPET_SUMMON_N206P"
TSMOD_D_FLIPPED = {}          -- unit name -> true, for summons now on the player team this battle
local tsmod_d_before = nil

local function tsmod_d_log(...)
  if TSLOG ~= nil then TSLOG(...) end
end

local function tsmod_d_units(tag)
  if TSLOG == nil or not TSLOG_ON then return end
  pcall(function()
    for _, u in pairs(GetUnitNameListAllIncludeDecoyAndTurret()) do
      local p = GetActorMapGridLocation(u)
      TSLOG(tag, u, "gop", GetUnitGopId(u), "team", GetTeamId(u), "ai", GetAIType(u),
            "at", p and p.X, p and p.Y, "dead", IsBattleUnitDead(u))
    end
  end)
end

local function tsmod_d_snapshot()
  local set = {}
  pcall(function()
    for _, u in pairs(GetUnitNameListAllIncludeDecoyAndTurret()) do set[u] = true end
  end)
  return set
end

local function tsmod_d_should_watch(activeUnit, gid)
  if gid == TSMOD_D_PUPPET then return true end
  return activeUnit ~= nil and TSMOD_D_FLIPPED[activeUnit] == true
end

local tsmod_d_orig_begin = BeginPlaySequenceForBattle
function BeginPlaySequenceForBattle(activeUnit, sequenceIndex, category, gopId)
  if tsmod_d_should_watch(activeUnit, gopId) then tsmod_d_before = tsmod_d_snapshot() end
  return tsmod_d_orig_begin(activeUnit, sequenceIndex, category, gopId)
end

local function tsmod_d_flip_new(activeUnit)
  local before = tsmod_d_before
  tsmod_d_before = nil
  if before == nil then return end
  for u, _ in pairs(tsmod_d_snapshot()) do
    if before[u] == nil and TSMOD_D_FLIPPED[u] == nil then
      local t0 = GetTeamId(u)
      ChangeUnitFriendlyType(u, true)
      local t1 = GetTeamId(u)
      if t1 == ETeamIdTEAM_A then TSMOD_D_FLIPPED[u] = true end
      tsmod_d_log("flip", u, "by", activeUnit, "team", t0, "->", t1, "ai", GetAIType(u))
    end
  end
end

local tsmod_d_orig_after = CheckTrapAndSlipAfterAction
function CheckTrapAndSlipAfterAction(activeUnit)
  local gid = (l_SelectedAttackInfo ~= nil) and l_SelectedAttackInfo.InfoGopId or nil
  tsmod_d_flip_new(activeUnit)
  if gid == TSMOD_D_PUPPET then tsmod_d_units("puppet: unit") end
  return tsmod_d_orig_after(activeUnit)
end

local tsmod_d_orig_active = OnActiveUnit
function OnActiveUnit(...)
  if TSLOG ~= nil and TSLOG_ON then
    pcall(function()
      local u = sys_info[SysInfo.BATTLE_ACTIVE_UNIT]
      TSLOG("turn", u, "gop", GetUnitGopId(u), "type", sys_info[SysInfo.BATTLE_ACTIVE_UNIT_TYPE],
            "team", GetTeamId(u), "ai", GetAIType(u))
    end)
  end
  return tsmod_d_orig_active(...)
end

-- [TSMod] Cryostasis on himself (user, Test 46 round, 2026-11-22): cast on Plinius himself, the forecast shows the full
-- heal but his HP doesn't change; on other allies the heal works and the statuses apply either way [tested]. Likely the
-- invincibility lands first on a self-cast and the heal is dropped [inferred]. After the action, if Plinius targeted
-- himself with Cryostasis, top his HP up directly: AddHP (+ed4430 -> +dda4c0) adds without status checks and clamps at
-- max HP (+dbc1b0) [read], so a large amount heals exactly to full.
local TSMOD_D_PLINIUS = "UNIT_MASTER_CH_M103"
local TSMOD_D_CRYOSTASIS = "BATTLE_ABILITY_STATUS_CURE_MAGIC_M103P"
local tsmod_d_cryo_after = CheckTrapAndSlipAfterAction
function CheckTrapAndSlipAfterAction(activeUnit)
  local gid = (l_SelectedAttackInfo ~= nil) and l_SelectedAttackInfo.InfoGopId or nil
  local selfcast = false
  if activeUnit == TSMOD_D_PLINIUS and gid == TSMOD_D_CRYOSTASIS and TSMOD_UnitAt ~= nil then
    local ok, tgt = pcall(function() return TSMOD_UnitAt(GetAttackTargetCoordinate()) end)
    selfcast = ok and tgt == TSMOD_D_PLINIUS
  end
  local r = tsmod_d_cryo_after(activeUnit)
  if selfcast and IsBattleUnitDead(TSMOD_D_PLINIUS) == false then
    local st = GetUnitStatus(TSMOD_D_PLINIUS)
    local before = st ~= nil and st.Hp or nil
    pcall(AddHP, TSMOD_D_PLINIUS, 99999)
    pcall(RequestUpdatePlayerInfo)
    local st2 = GetUnitStatus(TSMOD_D_PLINIUS)
    tsmod_d_log("cryostasis self-heal", before, "->", st2 ~= nil and st2.Hp or nil)
  end
  return r
end
