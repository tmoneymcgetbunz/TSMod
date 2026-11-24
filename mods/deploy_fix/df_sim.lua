-- Simulator of the game's deploy natives (exe +efd990/+d29de0/+d3d580/+d3dd30/+d31d60) for mods/deploy_fix.
local SRC = arg[1]
_G.TSLOG = nil
local slots, party, menu, calls, prohibited_set
local function reset(sq, partyNames)
  slots = {}; party = {}; menu = {}; calls = 0
  for _, n in ipairs(partyNames) do party[n] = true end
end
local function slotAt(x, y) for _, s in ipairs(slots) do if s.x == x and s.y == y then return s end end end
function AddInitialPosition(x, y, d) slots[#slots + 1] = {x = x, y = y} end
function AddProhibitedUnits(t) end
function IsPartyIn(n) return party[n] == true end
function GetUnitInitialPoint()
  local r = {}
  for _, s in ipairs(slots) do if s.name then r[#r + 1] = {ID = s.name, X = s.x, Y = s.y, DIR = 0} end end
  return r
end
local function realName(menuName) return menuName end
function ChangeSortieUnits(x, y, list)
  calls = calls + 1
  local inl = {}; for _, n in ipairs(list) do inl[n] = true end
  for _, s in ipairs(slots) do if s.name and not inl[s.name] then s.name = nil end end     -- +d29de0
  local rest = {}; for _, n in ipairs(list) do rest[#rest + 1] = n end
  local c = slotAt(x, y)
  if #menu > 0 and c and not c.name then                                                   -- +d32cc0/+d3d580
    local m = menu[1]
    if not party[m] then error("CRASH: cursor spawn of " .. m) end
    c.name = m
    local r2 = {}; for _, n in ipairs(rest) do if n ~= m then r2[#r2 + 1] = n end end; rest = r2
  end
  for _, n in ipairs(rest) do                                                               -- +d3dd30
    local placed = false
    for _, s in ipairs(slots) do if s.name == n then placed = true end end
    if not placed then
      local f; for _, s in ipairs(slots) do if not s.name then f = s; break end end
      if not f then break end
      if not party[n] then error("CRASH: d3dd30 spawn of " .. n) end
      f.name = n
    end
  end
end
-- load the two appends the way the game does: ClassBattlePreparation (after its own definitions) and BattlePreparation
ClassBattlePreparationBase = {}
function ClassBattlePreparationBase:CreateDataOnly() for _, s in ipairs(self.sq) do AddInitialPosition(s[1], s[2], 0) end end
function ClassBattlePreparationBase:SetupInittialPosition_Impl() for _, s in ipairs(self.sq) do AddInitialPosition(s[1], s[2], 0) end end
local function menuName(n)  -- the game's formula: P%03d of (character number - 1)
  local ids = {UNIT_MASTER_CH_M103 = 60, UNIT_MASTER_CH_N009 = 40, UNIT_MASTER_CH_N202 = 48, UNIT_MASTER_CH_N004 = 35, UNIT_MASTER_CH_N105 = 45}
  if ids[n] then return string.format("UNIT_MASTER_CH_P%03d", ids[n] - 1) end
  return n
end
dofile(SRC .. "/classprep_append.lua")
dofile(SRC .. "/battleprep_append.lua")

local function where(n) for i, s in ipairs(slots) do if s.name == n then return i, s.x, s.y end end end
local function state() local t = {} for i, s in ipairs(slots) do if s.name then t[#t + 1] = i .. ":" .. s.name:sub(16) end end return table.concat(t, " ") end
local fails = 0
local function check(cond, msg) if cond then print("  ok   " .. msg) else print("  FAIL " .. msg); fails = fails + 1 end end

local PARTY = {}
for i = 1, 30 do PARTY[#PARTY + 1] = string.format("UNIT_MASTER_CH_P%03d", i) end
for _, n in ipairs({"UNIT_MASTER_CH_M103", "UNIT_MASTER_CH_N009", "UNIT_MASTER_CH_N202", "UNIT_MASTER_CH_N004", "UNIT_MASTER_CH_N105"}) do PARTY[#PARTY + 1] = n end
local SQ = {}
for i = 1, 20 do SQ[#SQ + 1] = {i, 1} end

local function battle(initial)
  reset(SQ, PARTY)
  local inst = {sq = SQ}
  ClassBattlePreparationBase.CreateDataOnly(inst)
  ClassBattlePreparationBase.SetupInittialPosition_Impl(inst)   -- second setup call: the game ignores it, so must we
  for i, n in ipairs(initial) do slots[i].name = n end
end
local function userClose(cx, cy, list, picked)   -- the menu closes: its own list holds the picked units, menu-named
  menu = {}; for _, n in ipairs(picked) do menu[#menu + 1] = menuName(n) end
  calls = 0
  local ok, err = pcall(ChangeSortieUnits, cx, cy, list)
  return ok, err
end

print("A: Plinius removed from square 3, put back on square 3 (PC crash)")
battle({"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_M103", "UNIT_MASTER_CH_N009"})
userClose(3, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_N009"}, {})
local ok, err = userClose(3, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_N009", "UNIT_MASTER_CH_M103"}, {"UNIT_MASTER_CH_M103"})
check(ok, "no crash " .. tostring(err)); check(where("UNIT_MASTER_CH_M103") == 3, "Plinius on square 3: " .. state())

print("B: Sorsley added on a late empty square (12), 1 unit, stand-ins needed")
battle({"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002"})
ok, err = userClose(12, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_N202"}, {"UNIT_MASTER_CH_N202"})
check(ok, "no crash " .. tostring(err)); check(where("UNIT_MASTER_CH_N202") == 12, "Sorsley on square 12: " .. state())
local cnt = 0; for _, s in ipairs(slots) do if s.name then cnt = cnt + 1 end end
check(cnt == 3, "no stand-ins left (" .. cnt .. " units), " .. calls .. " calls")

print("C: Jerrom swapped in for Serenoa's neighbour on square 2, plus 2 more added (enough to fill before)")
battle({"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_P003"})
ok, err = userClose(2, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P003", "UNIT_MASTER_CH_N009", "UNIT_MASTER_CH_N004", "UNIT_MASTER_CH_P005"}, {"UNIT_MASTER_CH_N009", "UNIT_MASTER_CH_N004", "UNIT_MASTER_CH_P005"})
check(ok, "no crash " .. tostring(err)); check(where("UNIT_MASTER_CH_N009") == 2, "Jerrom on square 2: " .. state())

print("C2: same as C, cursor on square 6 (others fill 4 and 5 first, as the game would)")
battle({"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_P003"})
ok, err = userClose(6, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_P003", "UNIT_MASTER_CH_N009", "UNIT_MASTER_CH_N004", "UNIT_MASTER_CH_P005"}, {"UNIT_MASTER_CH_N009", "UNIT_MASTER_CH_N004", "UNIT_MASTER_CH_P005"})
check(ok, "no crash " .. tostring(err)); check(where("UNIT_MASTER_CH_N009") == 6, "Jerrom on square 6: " .. state())

print("D: base-game unit added on an empty square: untouched (cursor placement by the game)")
battle({"UNIT_MASTER_CH_P001"})
ok, err = userClose(9, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P007"}, {"UNIT_MASTER_CH_P007"})
check(ok and calls == 1 and where("UNIT_MASTER_CH_P007") == 9, "Roland-style add on square 9, 1 call: " .. state())

print("E: recruit added while the cursor is on a kept unit: game path, no crash")
battle({"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002"})
ok, err = userClose(2, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_P002", "UNIT_MASTER_CH_N105"}, {"UNIT_MASTER_CH_N105"})
check(ok and calls == 1, "no crash, 1 call: " .. state())

print("F: cursor off the deploy squares: game path")
battle({"UNIT_MASTER_CH_P001"})
ok, err = userClose(40, 9, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_N105"}, {"UNIT_MASTER_CH_N105"})
check(ok and calls == 1, "no crash, 1 call: " .. state())

print("G: no squares recorded (unknown battle setup): safe fallback")
battle({"UNIT_MASTER_CH_P001"}); rawset(_G, "TSMOD_DEPLOY_SQUARES", {})
ok, err = userClose(5, 1, {"UNIT_MASTER_CH_P001", "UNIT_MASTER_CH_N105"}, {"UNIT_MASTER_CH_N105"})
check(ok, "no crash (fallback) " .. state())

print(fails == 0 and "ALL PASS" or (fails .. " FAILED"))
