
-- [TSMod] Batch B2 hooks (mods/batchB2_final.md, 2026-11-19).
-- Gale of State (Thalas, BATTLE_ABILITY_CYCLONE_N103P): a wind cone (no thaw class: it crashed on a cone, Test 34). Before the cast (BeginPlaySequenceForBattle) the hook
--   reads which squares in the cone burn (IsBurning(x, y)) or are frozen (IsFreezing(x, y)) [read: +f0c250 / +f0c550 take
--   grid x, y]; after it (CheckTrapAndSlipAfterAction) each of those carries 2 squares further along the cast direction:
--   StartFire there (lights only burnable squares) or StartFreeze. The original
--   squares keep their state. Cone approximated as distance 1..3 from Thalas with half-width (distance - 1), like Whirlwind's.
-- Salt Tax (Sorsley, BATTLE_ABILITY_TORNADO_N202P): every enemy hit pays 10 x the battle's recommended level in gold
--   (GetLastMainBattleRecommendLevel; Lua can't read a unit's level), dropped as one purse on his square (Test 34b probe).
local TSMOD_B2_THALAS, TSMOD_B2_GALE = "UNIT_MASTER_CH_N103", "BATTLE_ABILITY_CYCLONE_N103P"
local TSMOD_B2_SORSLEY, TSMOD_B2_TAX = "UNIT_MASTER_CH_N202", "BATTLE_ABILITY_TORNADO_N202P"
TSMOD_B2_GALE_PLAN = nil

local function tsmod_b2_sign(v) if v > 0 then return 1 elseif v < 0 then return -1 end return 0 end

local function tsmod_b2_gale_snapshot(activeUnit)
  local me = GetActorMapGridLocation(activeUnit)
  local t = GetAttackTargetCoordinate()
  if t == nil then t = GetBattleCursorMapCoordinate() end
  if me == nil or t == nil then return end
  local dx, dy = t.X - me.X, t.Y - me.Y
  if math.abs(dx) >= math.abs(dy) then dx, dy = tsmod_b2_sign(dx), 0 else dx, dy = 0, tsmod_b2_sign(dy) end
  if dx == 0 and dy == 0 then return end
  local plan = {dx = dx, dy = dy, fire = {}, ice = {}}
  for d = 1, 3 do
    for l = -(d - 1), d - 1 do
      local x, y = me.X + dx * d + (dy ~= 0 and l or 0), me.Y + dy * d + (dx ~= 0 and l or 0)
      local okb, b = pcall(IsBurning, x, y)
      if okb and b == true then table.insert(plan.fire, {x, y}) end
      local okf, f = pcall(IsFreezing, x, y)
      if okf and f == true then table.insert(plan.ice, {x, y}) end
    end
  end
  TSMOD_B2_GALE_PLAN = plan
end

local function tsmod_b2_gale_carry()
  local p = TSMOD_B2_GALE_PLAN
  TSMOD_B2_GALE_PLAN = nil
  if p == nil then return end
  for _, c in ipairs(p.fire) do pcall(StartFire, c[1] + 2 * p.dx, c[2] + 2 * p.dy) end
  for _, c in ipairs(p.ice) do pcall(StartFreeze, c[1] + 2 * p.dx, c[2] + 2 * p.dy) end
end

local function tsmod_b2_salt_tax()
  local dmg = GetDamageInfo()
  if dmg == nil then return end
  local n = 0
  for u, _ in pairs(dmg) do
    local ok, team = pcall(GetTeamId, u)
    if ok and team == ETeamIdTEAM_B then n = n + 1 end
  end
  if n == 0 then return end
  local ok, lv = pcall(GetLastMainBattleRecommendLevel)
  if not ok or type(lv) ~= "number" or lv < 1 then lv = 30 end
  local total = n * 10 * math.floor(lv)
  -- Test 34b probe: the tribute lands as a purse on Sorsley's own square, so the game's own pick-up pop-up can show it
  -- (pick-ups are native; whether a unit standing on the square collects it is what the test checks).
  local purse = 50
  for _, a in ipairs({50, 100, 150, 200, 300, 400, 500, 750, 1000, 1250, 1500, 2000, 2500, 3000, 4000, 5000}) do
    if a <= total then purse = a end
  end
  local me = GetActorMapGridLocation(TSMOD_B2_SORSLEY)
  if me ~= nil then SpawnDropItem(me.X, me.Y, "ITEM_DROP_TSMOD_SALTTAX" .. purse .. "G") end
end

-- Winter's Touch (Plinius, BATTLE_ABILITY_ICE_MAGIC_M103P, user 2026-11-19): after the cast, wet + freeze every square within
--   2 (Manhattan) of the caster, his own included. Out-of-map squares are safe (tile lookup +f8ce90 bounds-checks) [read].
local TSMOD_B2_WINTER = "BATTLE_ABILITY_ICE_MAGIC_M103P"
local function tsmod_b2_winter(activeUnit)
  local me = GetActorMapGridLocation(activeUnit)
  if me == nil then return end
  for dx = -2, 2 do
    for dy = -2, 2 do
      if math.abs(dx) + math.abs(dy) <= 2 then
        pcall(StartPuddle, me.X + dx, me.Y + dy)
        pcall(StartFreeze, me.X + dx, me.Y + dy)
      end
    end
  end
end

local tsmod_b2_orig_begin = BeginPlaySequenceForBattle
function BeginPlaySequenceForBattle(activeUnit, sequenceIndex, category, gopId)
  if activeUnit == TSMOD_B2_THALAS and gopId == TSMOD_B2_GALE then pcall(tsmod_b2_gale_snapshot, activeUnit) end
  return tsmod_b2_orig_begin(activeUnit, sequenceIndex, category, gopId)
end

local tsmod_b2_orig_after = CheckTrapAndSlipAfterAction
function CheckTrapAndSlipAfterAction(activeUnit)
  local gid = (l_SelectedAttackInfo ~= nil) and l_SelectedAttackInfo.InfoGopId or nil
  if activeUnit == TSMOD_B2_THALAS and gid == TSMOD_B2_GALE then pcall(tsmod_b2_gale_carry) end
  if activeUnit == TSMOD_B2_SORSLEY and gid == TSMOD_B2_TAX then pcall(tsmod_b2_salt_tax) end
  if gid == TSMOD_B2_WINTER then pcall(tsmod_b2_winter, activeUnit) end
  return tsmod_b2_orig_after(activeUnit)
end
