-- [TSMod] Dragan bomb trap prototype (research pass item 3; TEST ONLY until the user approves a kit change).
-- Blasting Charge (BATTLE_ABILITY_BLASTING_CHARGE_N105P) = Steel Trap with its own trap actor (BP_ENV_co_TrapBomb_N105P:
-- the Explosives' model, bomb blast effect + sound, bear-trap meshes hidden). The vanilla trigger still hits the stepper
-- and ends their turn; this hook adds the blast. Facts used (docs/MECHANICS.md "Battle-hook natives"):
--   activationTrap(stepperName) runs trap triggers; ApplyDamage(unit, amount) deals flat damage to a battle unit;
--   StartFire(x, y) lights burnable tiles; GetUnitStatus(u) has Hp/PercentHp; GetUnitNameList(ETeamIdTEAM_B) = enemies.
-- Placements are remembered per battle (the Lua state resets on level load). Gold codes: +1 charge recorded, +10 blast fired,
-- +1000 error in the hook.
TSMOD_BOMB_TRAPS = TSMOD_BOMB_TRAPS or {}
local TSMOD_BC_ID = "BATTLE_ABILITY_BLASTING_CHARGE_N105P"
local TSMOD_BC_UNIT = "UNIT_MASTER_CH_N105"
local TSMOD_BC_RATE = 0.15   -- blast: 15% of each target's max HP

local function tsmod_bomb_blast(pos)
  pcall(SpawnEffectMapGridCoord, "hit_Fire000", pos.X, pos.Y, 0, 0, 1.5)
  local enemies = GetUnitNameList(ETeamIdTEAM_B) or {}
  for _, u in pairs(enemies) do
    local ok, c = pcall(GetActorMapGridLocation, u)
    if ok and c ~= nil and math.abs(c.X - pos.X) + math.abs(c.Y - pos.Y) <= 1 and IsBattleUnitDead(u) == false then
      local st = GetUnitStatus(u)
      if st ~= nil and st.Hp ~= nil and st.PercentHp ~= nil and st.PercentHp > 0 then
        local maxhp = math.floor(st.Hp * 100 / st.PercentHp + 0.5)
        pcall(ApplyDamage, u, math.max(1, math.floor(maxhp * TSMOD_BC_RATE)))
      end
    end
  end
  for _, d in ipairs({{0, 0}, {1, 0}, {-1, 0}, {0, 1}, {0, -1}}) do
    pcall(StartFire, pos.X + d[1], pos.Y + d[2])
  end
  pcall(AddGameMoney, 10)
end

local tsmod_bc_orig_after = CheckTrapAndSlipAfterAction
function CheckTrapAndSlipAfterAction(activeUnit)
  local ok = pcall(function()
    if activeUnit == TSMOD_BC_UNIT and l_SelectedAttackInfo ~= nil and l_SelectedAttackInfo.InfoGopId == TSMOD_BC_ID then
      local c = GetAttackTargetCoordinate()
      if c ~= nil then
        table.insert(TSMOD_BOMB_TRAPS, {X = c.X, Y = c.Y})
        AddGameMoney(1)
      end
    end
  end)
  if not ok then pcall(AddGameMoney, 1000) end
  return tsmod_bc_orig_after(activeUnit)
end

local tsmod_bc_orig_trap = activationTrap
function activationTrap(damageUnitName)
  local pos = nil
  pcall(function() pos = GetActorMapGridLocation(damageUnitName) end)
  local result = tsmod_bc_orig_trap(damageUnitName)
  local ok = pcall(function()
    if pos == nil then return end
    for i, t in ipairs(TSMOD_BOMB_TRAPS) do
      if t.X == pos.X and t.Y == pos.Y then
        table.remove(TSMOD_BOMB_TRAPS, i)
        tsmod_bomb_blast(pos)
        return
      end
    end
  end)
  if not ok then pcall(AddGameMoney, 1000) end
  return result
end

-- [TSMod] Dragan v2: Sticky Charge lights the ground (approved 2026-11-19).
-- The time-bomb blast is status-executed and applies no terrain effects [tested, Tests 19-20], so Lua does it:
--   1. After Dragan throws Sticky Charge (BATTLE_ABILITY_BOOBY_TRAP_N105P), remember every unit that now carries
--      the DELAY_DAMAGE status (EStatusEffect 34) [read: exe enum], with its tile and HP.
--   2. At several points in the turn flow (after auto-attacks, after damage, at turn start and turn end), check each
--      marked unit. Detonated = the status is gone AND (the unit is dead OR its HP dropped). Then StartFire on its last
--      tile and the 4 neighbours (StartFire only lights burnable tiles [read]). Status gone without HP loss = defused.
-- The blast path is [inferred]: AutoAttackImpl -> DamageUnitsTrigger; the polling covers either path.
-- Gold codes: +100 Sticky Charge target marked, +200 ignition fired, +1000 error in a hook (shared with the trap).
TSMOD_STICKY = TSMOD_STICKY or {}
local TSMOD_SC_ID = "BATTLE_ABILITY_BOOBY_TRAP_N105P"
local TSMOD_SC_STATUS = EStatusEffectDELAY_DAMAGE or 34

local function tsmod_sc_has(u)
  local ok, r = pcall(IsStatusEffectTriggered, u, TSMOD_SC_STATUS)
  return ok and r == true
end

local function tsmod_sc_hp(u)
  local st = GetUnitStatus(u)
  if st ~= nil and st.Hp ~= nil then return st.Hp end
  return nil
end

local function tsmod_sc_mark_targets()
  local names = {}
  local dmg = GetDamageInfo()
  if dmg ~= nil then
    for k, _ in pairs(dmg) do names[k] = true end
  end
  local c = GetAttackTargetCoordinate()
  if c ~= nil then
    for _, team in ipairs({ETeamIdTEAM_B, ETeamIdTEAM_A}) do
      for _, u in pairs(GetUnitNameList(team) or {}) do
        local ok, p = pcall(GetActorMapGridLocation, u)
        if ok and p ~= nil and p.X == c.X and p.Y == c.Y then names[u] = true end
      end
    end
  end
  for u, _ in pairs(names) do
    if IsBattleUnitDead(u) == false and tsmod_sc_has(u) then
      local p = GetActorMapGridLocation(u)
      TSMOD_STICKY[u] = {X = p.X, Y = p.Y, Hp = tsmod_sc_hp(u)}
      AddGameMoney(100)
    end
  end
end

local function tsmod_sc_ignite(pos)
  for _, d in ipairs({{0, 0}, {1, 0}, {-1, 0}, {0, 1}, {0, -1}}) do
    pcall(StartFire, pos.X + d[1], pos.Y + d[2])
  end
  pcall(AddGameMoney, 200)
end

function TSModStickyCheck()
  local ok = pcall(function()
    for u, m in pairs(TSMOD_STICKY) do
      local dead = IsBattleUnitDead(u) == true
      if not dead and tsmod_sc_has(u) then
        local p = GetActorMapGridLocation(u)            -- still carrying it: follow the bearer
        if p ~= nil then m.X = p.X; m.Y = p.Y end
        m.Hp = tsmod_sc_hp(u) or m.Hp
      else
        local hp = (not dead) and tsmod_sc_hp(u) or nil
        TSMOD_STICKY[u] = nil
        if dead or (hp ~= nil and m.Hp ~= nil and hp < m.Hp) then tsmod_sc_ignite(m) end
      end
    end
  end)
  if not ok then pcall(AddGameMoney, 1000) end
end

local tsmod_sc_orig_after = CheckTrapAndSlipAfterAction
function CheckTrapAndSlipAfterAction(activeUnit)
  local ok = pcall(function()
    if activeUnit == TSMOD_BC_UNIT and l_SelectedAttackInfo ~= nil and l_SelectedAttackInfo.InfoGopId == TSMOD_SC_ID then
      tsmod_sc_mark_targets()
    end
  end)
  if not ok then pcall(AddGameMoney, 1000) end
  local r = tsmod_sc_orig_after(activeUnit)
  TSModStickyCheck()
  return r
end

local tsmod_sc_orig_auto = AutoAttackImpl
function AutoAttackImpl(activeUnit)
  local r = tsmod_sc_orig_auto(activeUnit)
  TSModStickyCheck()
  return r
end

local tsmod_sc_orig_dut = DamageUnitsTrigger
function DamageUnitsTrigger(activeUnit, damageUnits)
  local r = tsmod_sc_orig_dut(activeUnit, damageUnits)
  TSModStickyCheck()
  return r
end

local tsmod_sc_orig_start = OnPreStartActiveUnitCommandSelect
function OnPreStartActiveUnitCommandSelect()
  local r = tsmod_sc_orig_start()
  TSModStickyCheck()
  return r
end

local tsmod_sc_orig_end = OnEndActiveUnitTurn
function OnEndActiveUnitTurn()
  local r = tsmod_sc_orig_end()
  TSModStickyCheck()
  return r
end
