"""Generates mods/c_hooks/src/battlebase_append.lua (Batch C, mods/batchC_proposal.md FINAL).

1. Smuggle (Clarus's weapon skill, BATTLE_ABILITY_ORDER_CHANGE_N301P), v7: no Quietus mode (user, 2026-11-20).
   History: v1 (command branch + reserve list) froze after the target was confirmed; v2-v6 ran the game's own Quietus
   flow, which works (v4+) but always shows the Quietus animation and the "Hidden Reserves" banner (Tests 37-37f).
   The kept v6 generator is make_hooks_v6.py (run it to revert).
   Facts behind v7 [read, re/decomp/xchg_*.c]: SetExchangeUnit / SetExchangedUnit / KeepExchangedUnit are plain setters
   on the battle manager's current-action record; none checks Quietus mode. The v1 freeze was the reserve-list screen
   opened from command-targeting state; v4 opened the same list after BattleOnOpenBattleOrderMenu and it worked.
   v7, in OnActiveUnitPlayer (vanilla copy + insertions):
     a. ExecStatus gets TSMOD_SMUGGLE_SELECT = 50;
     b. INPUT_ACTION (normal command targeting, which v1 showed works): on OPTIONAL_EFFECT_SELECT_EXCHANGE_UNIT, check
        CanExchangedUnitByAttackTarget as the Quietus does, then go to (c);
     c. TSMOD_SMUGGLE_SELECT: play a coin sound (a marker: the step was reached), bracket the reserve list with the
        Quietus menu's native open/close calls and its cursor calls, SetExchangeUnit(pick), mark the action used, and
        hand over to the normal EXEC_ACTION (his own animation; the engine spends TP for commands). Cancel = retarget.
   KeepExchangedUnit is called at the sequence start (BeginPlaySequenceForBattle wrapper), where the Quietus calls it.
   v8 (Test 37g: the whole flow ran, no swap; v6 in Quietus mode swaps): after the picks, ChangeTrumpMode(Hidden
   Reserves), then SetExchangedUnit(target unit) + SetExchangeUnit(pick) again (toggle TSMOD_SMUGGLE_LATE_TRUMP).
   Logger: TSLOG(...) appends to TSLOG_PATH (a dev path that mods/test_logging sets; nil in releases) via the io library; dispatcher states,
   INPUT_ACTION results and a list of natives are traced.
   v9 (Test 37h: v8 swaps, with the Quietus look; in Quietus mode the engine plays the Quietus row's name and attack
   row): Smuggle's own Quietus row BATTLE_ORDER_TSMOD_SMUGGLE (mod.json dt_edits) for the late ChangeTrumpMode.
   v10 (Test 37i: v9 shows his animation + banner but doesn't swap): two rows, alternated per use (A: Hidden
   Reserves' ability + his attack row; B: his ability + Hidden Reserves' attack row), to find what triggers the swap.
   v11 (Test 37j: with two extra Quietus rows the reserve list came up empty, even though the real Hidden Reserves
   works in that battle): one row only (A: Hidden Reserves' ability + his attack row); the target is logged before
   the list; CanExchangeUnits is checked first, as the Quietus menu does.
   Unknowns: whether the engine performs the swap for a non-Quietus action; whether the Quietus animation comes with
   the swap itself.
   The appended copy is compiled in the same chunk as the original file, so the file-level locals it uses are in scope.
   OnActiveUnitPlayer is called by name (BattleBase lines 1000/1016), so the redefinition takes over.
2. Fire the Deathsknell (Gustadolph, BATTLE_ABILITY_ERUPTION_N101P): the attack row plays the Explosives' blast
   (HitEffect Bomb000) on every unit hit; this hook also plays it, with the explosion sound, on the landing square
   after the shot, so an empty landing still booms. SpawnEffectMapGridCoord(id, x, y, height, rotate, scale) [read:
   shipped call sites].

Run: .venv/Scripts/python mods/c_hooks/make_hooks.py
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'decompiled', 'Newera_Handling', 'Battle', 'BattleBase.lua')
OUT = os.path.join(ROOT, 'mods', 'c_hooks', 'src', 'battlebase_append.lua')


def extract(src, name):
    i = src.index(f'\nfunction {name}()\n') + 1
    j = src.index('\nend\n', i) + len('\nend\n')       # the first column-0 "end" closes the function
    return src[i:j]


def patch(fn):
    def rep(old, new):
        nonlocal fn
        assert fn.count(old) == 1, ('anchor not unique / missing', old[:80])
        fn = fn.replace(old, new)
    # a. new state
    rep('    EXEC_BATTLE_ORDER = 17,\n', '    EXEC_BATTLE_ORDER = 17,\n    TSMOD_SMUGGLE_SELECT = 50,\n')
    # b. command branch: answer the exchange prompt
    rep('''    elseif resultMessageFromCPP == CPPFlowManagementResult.OPTIONAL_EFFECT_ATTACKTARGET_MOVE then
      return ExecStatus.INPUT_MOVE_ATTACKTARGET
    elseif resultMessageFromCPP == CPPFlowManagementResult.UNIT_WORK_CANCEL then
      if l_MenuBackupSelectedAttackInfo ~= nil then''',
        '''    elseif resultMessageFromCPP == CPPFlowManagementResult.OPTIONAL_EFFECT_ATTACKTARGET_MOVE then
      return ExecStatus.INPUT_MOVE_ATTACKTARGET
    elseif resultMessageFromCPP == CPPFlowManagementResult.OPTIONAL_EFFECT_SELECT_EXCHANGE_UNIT then
      -- [TSMod] Smuggle v7: a unit command with the exchange, no Quietus mode
      local reason = CanExchangedUnitByAttackTarget()
      if reason ~= 0 then
        BattleOrderCannotSelectExchangedUnitDialog(reason)
        return ExecStatus.INPUT_ACTION
      end
      return ExecStatus.TSMOD_SMUGGLE_SELECT
    elseif resultMessageFromCPP == CPPFlowManagementResult.UNIT_WORK_CANCEL then
      if l_MenuBackupSelectedAttackInfo ~= nil then''')
    # b2. Hidden Reserves (the Quietus itself) swapped out Idore's summoned Hierophant (user, 2026-11-23: no crash, a
    #     bench unit came in). CanExchangedUnitByAttackTarget lets summons through, as for Smuggle (cleanup item 19).
    #     Same party-member check as Smuggle; it refuses only when it finds a unit on the target tile that has no party
    #     record (the Hierophant UNIT_MASTER_CH_N201_2, her Pull Strings Automatons M071), else vanilla decides.
    rep('''      elseif workResultId == CPPFlowManagementResult.OPTIONAL_EFFECT_SELECT_EXCHANGE_UNIT then
        local reason = CanExchangedUnitByAttackTarget()''',
        '''      elseif workResultId == CPPFlowManagementResult.OPTIONAL_EFFECT_SELECT_EXCHANGE_UNIT then
        -- [TSMod] Hidden Reserves: summoned units (no party record) can't be swapped out
        local tsmod_hr_found, tsmod_hr_tgt = pcall(function() return TSMOD_UnitAt(GetAttackTargetCoordinate()) end)
        if tsmod_hr_found and tsmod_hr_tgt ~= nil then
          local tsmod_hr_ok, tsmod_hr_party = pcall(function() return IsPartyIn(GetUnitGopId(tsmod_hr_tgt)) == true end)
          if tsmod_hr_ok and tsmod_hr_party ~= true then
            TSLOG("smuggle: hidden reserves refused, not a party member", tsmod_hr_tgt)
            BattleOrderCannotSelectExchangedUnitDialog(1)
            return ExecStatus.EXEC_BATTLE_ORDER
          end
        end
        local reason = CanExchangedUnitByAttackTarget()''')
    # c. the reserve list, bracketed like the Quietus menu, then the normal action
    rep('  ExecFunc[ExecStatus.INPUT_SHIFT] = function()\n',
        '''  ExecFunc[ExecStatus.TSMOD_SMUGGLE_SELECT] = function()
    -- [TSMod] Smuggle v7
    pcall(PlaySE, "SE_BTL_ABL_N301_MONEY_IS_POWER_HIT", {X = 0, Y = 0, Z = 0})   -- marker: this step was reached
    TSLOG("smuggle: target before list", TSMOD_UnitAt(GetAttackTargetCoordinate()))
    -- Cleanup item 19 (crash in OnBattleUnitList, Test 38d session): CanExchangedUnitByAttackTarget lets a summoned
    -- unit through (Idore's Hierophant, no party record). Only party members can be smuggled out.
    local tsmod_tgt = TSMOD_UnitAt(GetAttackTargetCoordinate())
    local tsmod_ok, tsmod_party = pcall(function() return tsmod_tgt ~= nil and IsPartyIn(GetUnitGopId(tsmod_tgt)) == true end)
    if not (tsmod_ok and tsmod_party) then
      TSLOG("smuggle: refused, not a party member", tsmod_tgt)
      BattleOrderCannotSelectExchangedUnitDialog(1)
      return ExecStatus.INPUT_ACTION
    end
    if CanExchangeUnits() ~= 0 then             -- v11: the Quietus menu's own bench check
      BattleOrderNoExchangeUnitDialog()
      return ExecStatus.INPUT_ACTION
    end
    AttachBattleCursorToActiveUnit()
    BattleOnOpenBattleOrderMenu()
    OpenMenuBattleAll()
    -- Crash 2026-11-22 (Test 45b, old Idore fight; same stack as the Test 38d summon crash): the swap list the unit list
    -- shows is the battle-preparation unit list (+0x680), built only by UpdateBattlePreparationUnitListFromGameData
    -- (OnBattleSetup and the prep menus) and emptied by the end-of-preparation helper (+10c2100) [read]. In this list
    -- mode the engine has no empty-list check (+10bedb0 goes on to +1089d90, cursor row -1 -> +109788d) [read]. In the
    -- crash the battle had started through preparation and no Quietus had been used; where it worked, the battle was
    -- resumed or Hidden Reserves had been used first [log]. So rebuild the list from game data first, as OnBattleSetup
    -- does. Side effects of this native mid-battle are untested.
    if TSMOD_SMUGGLE_REFILL ~= false then
      TSLOG("smuggle: refill list")
      UpdateBattlePreparationUnitListFromGameData()
    end
    local smuggled = OnBattleUnitList(ULITLIST_ACTION_MODE.UNIT_LIST_ACTION_MODE_EXCHANGE)
    OnStartControlBattleCursor()
    SetBattleCursorVisibility(true)
    BattleOnCloseBattleOrderMenu()
    if smuggled == nil or smuggled == "" then
      return ExecStatus.INPUT_ACTION
    end
    -- v8 (Test 37g: v7 ran the whole flow but no swap happened; v6, in Quietus mode, swaps): enter Hidden Reserves'
    -- Quietus mode only now, after the picks, then record both units again (ChangeTrumpMode may reset the action record).
    local tgt = TSMOD_UnitAt(GetAttackTargetCoordinate())
    TSLOG("smuggle: target", tgt, "pick", smuggled)
    TSMOD_SMUGGLE_USES = TSMOD_SMUGGLE_USES + 1
    local order = TSMOD_SMUGGLE_ORDER
    if TSMOD_SMUGGLE_ALTERNATE and TSMOD_SMUGGLE_USES % 2 == 0 then order = TSMOD_SMUGGLE_ORDER_B end
    TSLOG("smuggle: use", TSMOD_SMUGGLE_USES, "order", order)
    if TSMOD_SMUGGLE_LATE_TRUMP then pcall(ChangeTrumpMode, order) end
    if tgt ~= nil then SetExchangedUnit(tgt) end
    SetExchangeUnit(smuggled)
    TSMOD_SMUGGLE_PENDING = true
    CloseMenuBattleAll()
    SetLastUseAbilityId(activeUnit)
    sys_info[SysInfo.ATTACK_COMMAND_USED] = 1
    sys_info[SysInfo.BATTLE_UNIT_TURN_ACTED] = 1
    SetSysGlobal(SysGlobal.BATTLE_STEP_FOR_SERIALIZE, ENUM_CurrentFlowState.ACTION_USED)
    return ExecStatus.EXEC_ACTION
  end
  ExecFunc[ExecStatus.INPUT_SHIFT] = function()
''')
    rep('    local nextExecStatus = ExecFunc[execStatus]()\n', '    TSLOG("state ->", TSMOD_StateName(execStatus), activeUnit)\n    local nextExecStatus = ExecFunc[execStatus]()\n')
    rep('  local ExecFunc = {}\n',
        '  TSMOD_EXEC_STATUS_NAMES = {}\n  for k, v in pairs(ExecStatus) do TSMOD_EXEC_STATUS_NAMES[v] = k end\n  local ExecFunc = {}\n')
    rep('    local resultMessageFromCPP = CPPFlowManagementResult[_retry(PeekMessage)]\n    local attackCommand = GetCurrentAttackCommand()\n',
        '    local resultMessageFromCPP = CPPFlowManagementResult[_retry(PeekMessage)]\n'
        '    TSLOG("INPUT_ACTION result", resultMessageFromCPP, l_SelectedAttackInfo and l_SelectedAttackInfo.InfoGopId)\n'
        '    local attackCommand = GetCurrentAttackCommand()\n')
    return fn


HOOKS = '''
-- [TSMod] Batch C hooks (generated by mods/c_hooks/make_hooks.py; see its docstring).

-- Logger (test 37h): game Lua appends lines to a file, if its io library is registered (the exe contains it [read]).
-- No file after a test = io is unavailable. Nothing here can break the game: every write is inside pcall.
TSLOG_PATH = nil     -- test builds: mods/test_logging sets the dev log path (never shipped)
TSLOG_ON = false     -- off in release builds; test builds append mods/test_logging (TSLOG_ON = true)
local function tslog_args(...)
  local n, out = select("#", ...), {}
  for i = 1, n do out[#out + 1] = tostring((select(i, ...))) end
  return table.concat(out, " ")
end
function TSLOG(...)
  if not TSLOG_ON then return end
  local line = tslog_args(...)
  pcall(function()
    local f = io.open(TSLOG_PATH, "a")
    if f == nil then return end
    f:write(string.format("%10.3f  ", os.clock()), line, "\\n")
    f:close()
  end)
end
TSLOG("=== BattleBase loaded", (os ~= nil and os.date ~= nil) and os.date() or "")
function TSMOD_StateName(v)
  return (TSMOD_EXEC_STATUS_NAMES ~= nil and TSMOD_EXEC_STATUS_NAMES[v]) or tostring(v)
end
function TSMOD_UnitAt(c)
  if c == nil then return nil end
  for _, u in pairs(GetUnitNameListAllIncludeDecoyAndTurret()) do
    local p = GetActorMapGridLocation(u)
    if p ~= nil and p.X == c.X and p.Y == c.Y then return u end
  end
  return nil
end
TSMOD_SMUGGLE_LATE_TRUMP = true      -- v8: Quietus mode only after the picks (the swap needs it, Test 37h)
TSMOD_SMUGGLE_ORDER = "BATTLE_ORDER_TSMOD_SMUGGLE"     -- v10 row A: Hidden Reserves' ability + his attack row
TSMOD_SMUGGLE_ORDER_B = "BATTLE_ORDER_TSMOD_SMUGGLE_B" -- v10 row B: his ability + Hidden Reserves' attack row
TSMOD_SMUGGLE_ALTERNATE = false  -- v10 test: odd uses = A, even uses = B ("BATTLE_ORDER_TEST_CHANGE" = v8)
TSMOD_SMUGGLE_USES = 0

local TSMOD_C_BELL = "BATTLE_ABILITY_ERUPTION_N101P"
local TSMOD_C_SMUGGLE_ID = "BATTLE_ABILITY_ORDER_CHANGE_N301P"
TSMOD_SMUGGLE_PENDING = false
TSMOD_C_BELL_AT = nil

local tsmod_c_orig_begin = BeginPlaySequenceForBattle
function BeginPlaySequenceForBattle(activeUnit, sequenceIndex, category, gopId)
  if gopId == TSMOD_C_SMUGGLE_ID and TSMOD_SMUGGLE_PENDING then
    TSMOD_SMUGGLE_PENDING = false
    KeepExchangedUnit()          -- the Quietus calls it here: after OnStartUnitAction, before the sequence
  end
  if gopId == TSMOD_C_BELL then
    local ok, t = pcall(GetAttackTargetCoordinate)
    if ok and t ~= nil then TSMOD_C_BELL_AT = {t.X, t.Y} end
  end
  return tsmod_c_orig_begin(activeUnit, sequenceIndex, category, gopId)
end

local tsmod_c_orig_after = CheckTrapAndSlipAfterAction
function CheckTrapAndSlipAfterAction(activeUnit)
  local gid = (l_SelectedAttackInfo ~= nil) and l_SelectedAttackInfo.InfoGopId or nil
  if gid == TSMOD_C_BELL and TSMOD_C_BELL_AT ~= nil then
    local at = TSMOD_C_BELL_AT
    TSMOD_C_BELL_AT = nil
    pcall(SpawnEffectMapGridCoord, "Bomb000", at[1], at[2], 0, 0, 1.5)
    pcall(PlaySE, "SE_GIM_BOMB_EXPLODE", {X = 0, Y = 0, Z = 0})
  end
  return tsmod_c_orig_after(activeUnit)
end

-- Tracer: log calls to these functions (args and results); Test 37h: wrapping _G missed the script-defined ones. Wrappers don't use pcall, so coroutine waits pass through.
local function tsmod_pack(...) return {n = select("#", ...), ...} end
for _, name in ipairs({"ChangeTrumpMode", "SetExchangeUnit", "SetExchangedUnit", "KeepExchangedUnit", "ConsumeKP",
    "BeginPlaySequenceForBattle", "CanExchangedUnitByAttackTarget", "CanExchangeUnits", "OnStartUnitAction",
    "GetReplaceUnit", "ChangeBattleUnitAttackMode", "ChangeBattleUnitMoveMode", "BattleOnOpenBattleOrderMenu",
    "BattleOnCloseBattleOrderMenu", "OnBattleUnitList", "CheckTrapAndSlipAfterOrder", "CheckTrapAndSlipAfterAction",
    "SetLastUseAbilityId", "AddTP", "AddKP", "IsExchangedUnit"}) do
  local env = getfenv(1)   -- the game runs scripts in their own environment: Lua-defined functions live here, not in _G
  local f = env[name]
  if type(f) == "function" then
    env[name] = function(...)
      TSLOG("call", name, tslog_args(...))
      local r = tsmod_pack(f(...))
      TSLOG(" ret", name, tslog_args(unpack(r, 1, r.n)))
      return unpack(r, 1, r.n)
    end
  end
end

-- Smuggle v8: OnActiveUnitPlayer = vanilla + the command-branch exchange (see make_hooks.py)
'''


if __name__ == '__main__':
    src = open(SRC, encoding='utf-8').read()
    fn = patch(extract(src, 'OnActiveUnitPlayer'))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(HOOKS + fn)
    print('wrote', OUT, len(fn.splitlines()), 'lines of OnActiveUnitPlayer')
