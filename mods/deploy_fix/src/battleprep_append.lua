-- [TSMod] deploy_fix (2/2): keep cursor placement on the deploy screen working for TSMod recruits.
-- The game (exe +efd990) puts the first unit picked in the unit-list menu on the square under the cursor, but takes its
-- name from the menu's own list, which rebuilds names as "UNIT_MASTER_CH_P%03d" from the character number. For a
-- recruit that name doesn't exist and the game crashes (mods/TESTING.md, 2026-11-23). Every other unit is placed on
-- the first empty square in the battle's square order (+d3dd30), using the real names from the script's list.
-- So when that crash case applies, this places the units in an order (with stand-ins if needed) that makes the game's
-- safe path put the added unit on the cursor square: the same result as the game's own cursor placement.
local tsmod_df_env = getfenv(1)
local tsmod_df_place = tsmod_df_env.ChangeSortieUnits

local function tsmod_df_log(...)
  local f = rawget(tsmod_df_env, "TSMOD_RLOG")
  if type(f) == "function" then pcall(f, ...) end
  if TSLOG ~= nil then pcall(TSLOG, ...) end
end

-- A name the menu can rebuild correctly: the base-game party (UNIT_MASTER_CH_P001..P030).
local function tsmod_df_menu_safe(name)
  local n = string.match(name, "^UNIT_MASTER_CH_P(%d%d%d)$")
  return n ~= nil and tonumber(n) >= 1 and tonumber(n) <= 30
end

-- Returns the list of calls to make ({x, y, list} each), or nil to call the game as it is.
local function tsmod_df_plan(x, y, list)
  if type(list) ~= "table" or type(x) ~= "number" or type(y) ~= "number" then return nil end
  local occ = GetUnitInitialPoint()                    -- occupied deploy squares, in the game's order: {ID, X, Y, DIR}
  if type(occ) ~= "table" then return nil end
  local inlist, onfield = {}, {}
  for _, n in ipairs(list) do inlist[tostring(n)] = true end
  for _, o in ipairs(occ) do onfield[tostring(o.ID)] = o end
  local new = {}
  for _, n in ipairs(list) do
    if onfield[tostring(n)] == nil then new[#new + 1] = tostring(n) end
  end
  local risky = false
  for _, n in ipairs(new) do if not tsmod_df_menu_safe(n) then risky = true end end
  if not risky then return nil end                      -- only base-game units added: the game's names are right

  -- From here on, never let the game place on the cursor square itself: (-1, -1) is not a deploy square.
  local fallback = {{-1, -1, list}}
  local squares = rawget(_G, "TSMOD_DEPLOY_SQUARES")
  if type(squares) ~= "table" or #squares == 0 then return fallback, "no squares recorded" end
  local index = {}
  for i, s in ipairs(squares) do
    local k = s[1] .. "," .. s[2]
    if index[k] == nil then index[k] = i end
  end
  -- Check the recorded order against the game's: every occupied square known, in increasing order.
  local last = 0
  for _, o in ipairs(occ) do
    local i = index[o.X .. "," .. o.Y]
    if i == nil or i <= last then return fallback, "square order mismatch" end
    last = i
  end
  local ci = index[x .. "," .. y]
  if ci == nil then return {{x, y, list}} end          -- cursor not on a deploy square: the game skips cursor placement
  local taken = {}
  for _, o in ipairs(occ) do
    if inlist[tostring(o.ID)] then taken[index[o.X .. "," .. o.Y]] = true end
  end
  if taken[ci] then return {{x, y, list}} end          -- cursor square stays occupied: the game skips cursor placement
  -- Crash case. Empty squares before the cursor square, in the game's order.
  local before = 0
  for i = 1, ci - 1 do if not taken[i] then before = before + 1 end end
  local unit, others = new[1], {}
  for i = 2, #new do others[#others + 1] = new[i] end
  local kept = {}
  for _, n in ipairs(list) do if onfield[tostring(n)] ~= nil then kept[#kept + 1] = tostring(n) end end
  local order = {}
  for _, n in ipairs(kept) do order[#order + 1] = n end
  if #others >= before then
    for i = 1, before do order[#order + 1] = others[i] end
    order[#order + 1] = unit
    for i = before + 1, #others do order[#order + 1] = others[i] end
    return {{-1, -1, order}}, unit .. " via order"
  end
  -- Not enough added units to fill the squares before the cursor: stand-ins (undeployed base-game party members not
  -- greyed out in this battle) fill them for one call and are removed by the next.
  local prohibited = rawget(_G, "TSMOD_DEPLOY_PROHIBITED") or {}
  local need, fillers = before - #others, {}
  for i = 1, 30 do
    if #fillers >= need then break end
    local n = string.format("UNIT_MASTER_CH_P%03d", i)
    if not inlist[n] and onfield[n] == nil and not prohibited[n] and IsPartyIn(n) == true then
      fillers[#fillers + 1] = n
    end
  end
  if #fillers < need then return fallback, "not enough stand-ins" end
  local first = {}
  for _, n in ipairs(order) do first[#first + 1] = n end
  for _, n in ipairs(others) do first[#first + 1] = n end
  for _, n in ipairs(fillers) do first[#first + 1] = n end
  first[#first + 1] = unit
  local final = {}
  for _, n in ipairs(order) do final[#final + 1] = n end
  for _, n in ipairs(others) do final[#final + 1] = n end
  final[#final + 1] = unit
  return {{-1, -1, first}, {-1, -1, final}}, unit .. " via " .. #fillers .. " stand-ins"
end

if type(tsmod_df_place) == "function" then
  tsmod_df_env.ChangeSortieUnits = function(x, y, list, ...)
    local ok, calls, why = pcall(tsmod_df_plan, x, y, list)
    if not ok then
      tsmod_df_log("deploy_fix: Lua error", tostring(calls))
      calls = {{-1, -1, list}}                         -- safe default: no cursor placement
    end
    if calls == nil then return tsmod_df_place(x, y, list, ...) end
    if why ~= nil then tsmod_df_log("deploy_fix:", why, "cursor", tostring(x), tostring(y)) end
    local r
    for _, c in ipairs(calls) do r = {tsmod_df_place(c[1], c[2], c[3], ...)} end
    return unpack(r)
  end
end
