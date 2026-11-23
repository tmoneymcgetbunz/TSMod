
-- [TSMod] Landroi: Heroic End (user, 2026-11-19; mods/landroi_last_breath_proposal.md).
-- A 0-TP self-cast weapon skill (BATTLE_ABILITY_POWER_SHOOT_N008P) that does nothing on its own. After it resolves:
--   1. every living ally (team A, not Landroi) gets two buff sets via AddBuffDebuffToUnit(unit, attackParamId)
--      [read: +ed40b0 applies that AttackParam's BuffEffectAtk]: STR/INT/DEF/MDF and DEX/AGI/LUK/SPD, level II, 2 turns;
--   2. Landroi takes damage equal to his current HP (ApplyDamage) and the KO goes through the game's own
--      "fell on his own turn" path (CheckTriggerHPZeroFromSlipDamage, else CheckHpZero; as OnPreStartActiveUnitCommandSelect).
-- Returns 0 so the action loop ends his turn. Gold codes (distinct from Dragan's 1/10/100/200/1000): +10000 buffs applied,
-- +20000 Landroi is down, +40000 Landroi still alive after the damage, +80000 error.
local TSMOD_HE_IDS = {["BATTLE_ABILITY_POWER_SHOOT_N008P"] = true, ["BATTLE_ABILITY_HEROIC_END_B_N008P"] = true}  -- B: Test 32 probe only
local TSMOD_HE_UNIT = "UNIT_MASTER_CH_N008"
local TSMOD_HE_SETS = {"BATTLE_ATTACKPARAM_HEROIC_END_A_N008P", "BATTLE_ATTACKPARAM_HEROIC_END_B_N008P"}

local function tsmod_he_resolve()
  for _, u in pairs(GetUnitNameList(ETeamIdTEAM_A) or {}) do
    if u ~= TSMOD_HE_UNIT and IsBattleUnitDead(u) == false then
      for _, ap in ipairs(TSMOD_HE_SETS) do
        AddBuffDebuffToUnit(u, ap)
      end
      local ok, p = pcall(GetActorMapGridLocation, u)
      if ok and p ~= nil then pcall(SpawnEffectMapGridCoord, "Buff000", p.X, p.Y, 0, 0, 1.0) end
    end
  end
  AddGameMoney(10000)
  -- Test 32: the skill's own attack may already have KO'd him through the normal damage path (then the game handles it).
  if IsBattleUnitDead(TSMOD_HE_UNIT) == true then return end
  local st = GetUnitStatus(TSMOD_HE_UNIT)
  if st ~= nil and st.Hp ~= nil and st.Hp > 0 then
    ApplyDamage(TSMOD_HE_UNIT, st.Hp)
  end
  if IsBattleUnitDead(TSMOD_HE_UNIT) == true then
    AddGameMoney(20000)
    RequestUpdatePlayerInfo()
    if CheckTriggerHPZeroFromSlipDamage(TSMOD_HE_UNIT) == false then
      CheckHpZero(TSMOD_HE_UNIT)
    end
  else
    AddGameMoney(40000)
  end
end

local tsmod_he_orig_after = CheckTrapAndSlipAfterAction
function CheckTrapAndSlipAfterAction(activeUnit)
  local fire = activeUnit == TSMOD_HE_UNIT and l_SelectedAttackInfo ~= nil and TSMOD_HE_IDS[l_SelectedAttackInfo.InfoGopId] == true
  local r = tsmod_he_orig_after(activeUnit)
  if fire then
    local ok = pcall(tsmod_he_resolve)
    if not ok then pcall(AddGameMoney, 80000) end
    return 0
  end
  return r
end
