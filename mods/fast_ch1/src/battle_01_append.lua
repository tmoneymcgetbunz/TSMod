-- [TSMod] fast_ch1: optional fast Chapter 1 battle (user, 2026-11-22; mods/fast_ch1_proposal.md).
-- On only when the save's flag TEST_FLAG is set (the save editor's "Fast Chapter 1 battle" checkbox; the game itself
-- never sets or reads that leftover developer flag). Off: this battle is exactly vanilla.
-- Inside the battle only: every enemy starts with 1 HP, the battle is won as soon as any enemy is defeated, and the
-- in-battle talk and tutorial pop-up are skipped. The cutscenes before and after the battle (its scene block: joins,
-- Roland leaving, costume changes) are untouched. Taken from the tested test kit (mods/testkit_ch1), made conditional,
-- with the 1 HP set at spawn instead of the kit's growth-table edit (which reached other battles too).
local tsmod_fast_ok, tsmod_fast_on = pcall(function() return GetFlag(Flag.TEST_FLAG) == true end)
tsmod_fast_on = tsmod_fast_ok and tsmod_fast_on
if TSLOG ~= nil then pcall(TSLOG, "fast_ch1", tsmod_fast_on) end

if tsmod_fast_on then
  -- Won as soon as any enemy is defeated (the kit's VictoryFunc).
  BattleEndCheckTable = BattleEndCheckTable or {}
  function BattleEndCheckTable.VictoryFunc(CheckVictory)
    return GetDefeatUnitCountByOccupantType(UNIT_TYPE_ENEMY) >= 1
  end

  -- Every enemy at 1 HP, after vanilla's own post-spawn setup (AI settings).
  local tsmod_fast_post = ClassBattle.PostSpawnUnit_Implementation
  function ClassBattle:PostSpawnUnit_Implementation()
    tsmod_fast_post(self)
    for _, u in pairs(GetUnitNameList(ETeamIdTEAM_B) or {}) do
      local ok, st = pcall(GetUnitStatus, u)
      if ok and st ~= nil and st.Hp ~= nil and st.Hp > 1 then pcall(AddHP, u, 1 - st.Hp) end
    end
  end

  -- Opening talk and tutorial pop-up removed; menu and camera handling as vanilla's Introduction (the kit's version).
  function Introduction()
    OnStartEventInBattle()
    local tmpInputMode = SetActionInputMode(INPUT_MODE_GAME_UI)
    CloseMenuBattleAll()
    SetBattleCursorVisibility(false)
    OpenMenuBattleAll()
    SetBattleCursorVisibility(true)
    SetActionInputMode(tmpInputMode)
    ChangeTraceCamera(CAMERA_BLEND_CUBIC, 0.4, 2)
    _retry(SYS_WaitStageCameraBlend)
    OnEndEventInBattle()
  end

  -- Per-turn talk removed; the enemy AI calls kept (the kit's versions).
  function g_ActivePlayerUnitFunction(ActiveUnitName)
  end
  function g_ActiveAIUnitFunction(ActiveAIUnitName)
    CallUnitAIFunc(ActiveAIUnitName)
    AISetNormalAbilityProbability({
      {
        Id = "BATTLE_ABILITY_LONG_FIRE_ARROW",
        Prob = 20
      }
    })
  end
  function g_TurnEndAIUnitFunction(ActiveAIUnitName)
  end
  function g_TurnEndPlayerUnitFunction(ActiveUnitName)
  end

  -- Travis's and Trish's defeat and first-attack lines (talk only; their flags are battle-local) [read].
  g_TriggerHPZeroTable = {
    {"UNIT_MASTER_CH_P014", function() end},
    {"UNIT_MASTER_CH_P015", function() end}
  }
  g_EventFirstAttackTriggerBeforeTable = {}
end
