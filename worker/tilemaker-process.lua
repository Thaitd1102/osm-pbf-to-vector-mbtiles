-- node_keys: chỉ key, không phải key=value
node_keys = {"highway", "amenity", "place", "name", "operator", "toll", "payment", "payment:etc", "addr:full", "addr:province", "road", "maps_vietnam:status", "maps_vietnam:status_note", "maps_vietnam:confidence"}
way_keys  = {"highway", "toll", "waterway", "boundary", "admin_level", "natural", "water", "landuse", "leisure"}

-- ── Road types ──────────────────────────────────────────────
road_type = {
  motorway=true,      motorway_link=true,
  trunk=true,         trunk_link=true,
  primary=true,       primary_link=true,
  secondary=true,     tertiary=true,
  residential=true,   unclassified=true
}

-- ── Waterway: chỉ loại lớn ──────────────────────────────────
waterway_type = {
  river=true, canal=true, stream=true
  -- bỏ: drain, ditch, tidal_channel, derelict_canal
}

-- ── POI cho navigation ──────────────────────────────────────
poi_list = {
  fuel=true, parking=true, hospital=true, police=true
}

-- ── Place: bỏ suburb — quá nhiều, ít giá trị navigation ────
place_type = {
  city=true, town=true, village=true
  -- bỏ suburb: hàng nghìn entry ở Vietnam
}

-- ── Admin level cần render boundary ────────────────────────
-- 2=quốc gia, 4=tỉnh, 6=huyện — bỏ 8=xã (quá nhiều)
admin_level_ok = {["2"]=true, ["4"]=true, ["6"]=true}

landuse_type = {
  residential=true, commercial=true, industrial=true, retail=true,
  grass=true, meadow=true, farmland=true, orchard=true, cemetery=true
}

landcover_type = {
  wood=true, forest=true, scrub=true, heath=true, grassland=true, wetland=true
}

function node_function()
  local highway = Find("highway")
  if highway == "toll_gantry" then
    Layer("toll_gantry", false)
    local name = Find("name")
    local operator = Find("operator")
    local toll = Find("toll")
    local payment = Find("payment")
    local payment_etc = Find("payment:etc")
    local address = Find("addr:full")
    local province = Find("addr:province")
    local road = Find("road")
    local status = Find("maps_vietnam:status")
    local status_note = Find("maps_vietnam:status_note")
    local confidence = Find("maps_vietnam:confidence")
    if name ~= "" then Attribute("name", name) end
    if operator ~= "" then Attribute("operator", operator) end
    if toll ~= "" then Attribute("toll", toll) end
    if payment ~= "" then Attribute("payment", payment) end
    if payment_etc ~= "" then Attribute("payment_etc", payment_etc) end
    if address ~= "" then Attribute("address", address) end
    if province ~= "" then Attribute("province", province) end
    if road ~= "" then Attribute("road", road) end
    if status ~= "" then Attribute("status", status) end
    if status_note ~= "" then Attribute("status_note", status_note) end
    if confidence ~= "" then Attribute("confidence", confidence) end
    return
  end

  local amenity = Find("amenity")
  if poi_list[amenity] then
    Layer("pois", false)
    Attribute("amenity", amenity)
    local name = Find("name")
    if name ~= "" then Attribute("name", name) end
    return
  end

  local place = Find("place")
  if place_type[place] then
    Layer("place", false)
    Attribute("place", place)
    local name = Find("name")
    if name ~= "" then Attribute("name", name) end
  end
end

function way_function()
  local natural = Find("natural")
  if natural == "water" or natural == "bay" then
    Layer("water", true)
    local water = Find("water")
    Attribute("class", water ~= "" and water or natural)
    return
  end

  if natural == "wood" or natural == "forest" or natural == "scrub" or natural == "wetland" then
    Layer("landcover", true)
    Attribute("class", natural)
    return
  end

  local landuse = Find("landuse")
  if landuse_type[landuse] then
    Layer("landuse", true)
    Attribute("class", landuse)
    return
  end

  local leisure = Find("leisure")
  if leisure == "park" or leisure == "garden" or leisure == "golf_course" then
    Layer("landuse", true)
    Attribute("class", leisure)
    return
  end

  -- Waterway: chỉ loại lớn
  local waterway = Find("waterway")
  if waterway_type[waterway] then
    Layer("waterway", false)
    Attribute("waterway", waterway)
    return  -- return sớm, không check tiếp
  end

  -- Boundary: chỉ admin level 2, 4, 6
  if Find("boundary") == "administrative" then
    local level = Find("admin_level")
    if admin_level_ok[level] then
      Layer("boundary", false)
      Attribute("admin_level", level)
    end
    return
  end

  -- Transportation
  local highway = Find("highway")
  if road_type[highway] then
    Layer("transportation", false)
    Attribute("highway", highway)

    local name     = Find("name")
    local oneway   = Find("oneway")
    local maxspeed = Find("maxspeed")
    local toll     = Find("toll")

    if name ~= ""     then Attribute("name", name)         end
    if oneway ~= ""   then Attribute("oneway", oneway)     end
    if maxspeed ~= "" then Attribute("maxspeed", maxspeed) end
    if toll == "yes"  then Attribute("toll", "yes")        end
    return
  end
end
