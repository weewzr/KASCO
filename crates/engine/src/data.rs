//! Official datasets, compiled into the binary so the engine needs no file access.
use std::sync::OnceLock;

const SITES: &str = include_str!("../../../data/biomass_sites.csv");
const AIRPORTS: &str = include_str!("../../../data/airports.csv");
const ROAD: &str = include_str!("../../../data/road_km.csv");
const LAND: &str = include_str!("../../../data/borneo_land.json");
const EARTH_KM: f64 = 6371.0;

#[derive(Clone, Debug)]
pub struct Site {
    pub id: String,
    pub province: String,
    pub district: String,
    pub kt: f64,
    pub lat: f64,
    pub lon: f64,
}

#[derive(Clone, Debug)]
pub struct Airport {
    pub iata: String,
    pub name: String,
    pub city: String,
    pub lat: f64,
    pub lon: f64,
    pub demand: f64,
}

pub struct Network {
    pub sites: Vec<Site>,
    pub airports: Vec<Airport>,
    pub road_ids: Vec<String>,
    pub road: Vec<Vec<f64>>,
}

pub fn haversine(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let (p1, p2) = (lat1.to_radians(), lat2.to_radians());
    let (dp, dl) = (p2 - p1, (lon2 - lon1).to_radians());
    let h = (dp / 2.0).sin().powi(2) + p1.cos() * p2.cos() * (dl / 2.0).sin().powi(2);
    2.0 * EARTH_KM * h.sqrt().asin()
}

fn parse() -> Network {
    let sites = SITES
        .lines()
        .skip(1)
        .filter(|l| !l.trim().is_empty())
        .map(|l| {
            let c: Vec<&str> = l.trim().split(',').collect();
            Site {
                id: c[0].into(),
                province: c[1].into(),
                district: c[2].into(),
                kt: c[3].parse().unwrap(),
                lat: c[5].parse().unwrap(),
                lon: c[6].parse().unwrap(),
            }
        })
        .collect();
    let airports = AIRPORTS
        .lines()
        .skip(1)
        .filter(|l| !l.trim().is_empty())
        .map(|l| {
            let c: Vec<&str> = l.trim().split(',').collect();
            Airport {
                iata: c[0].into(),
                name: c[2].into(),
                city: c[3].into(),
                lat: c[4].parse().unwrap(),
                lon: c[5].parse().unwrap(),
                demand: c[6].parse().unwrap(),
            }
        })
        .collect();
    let mut lines = ROAD.lines();
    let road_ids: Vec<String> = lines.next().unwrap().trim().split(',').skip(1).map(String::from).collect();
    let road = lines
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.trim().split(',').skip(1).map(|v| v.parse::<f64>().unwrap_or(f64::NAN)).collect())
        .collect();
    Network { sites, airports, road_ids, road }
}

pub fn network() -> &'static Network {
    static NET: OnceLock<Network> = OnceLock::new();
    NET.get_or_init(parse)
}

fn rings() -> &'static Vec<Vec<[f64; 2]>> {
    static R: OnceLock<Vec<Vec<[f64; 2]>>> = OnceLock::new();
    R.get_or_init(|| serde_json::from_str(LAND).unwrap())
}

/// Ray casting against the Natural Earth land rings.
pub fn on_land(lat: f64, lon: f64) -> bool {
    for ring in rings() {
        let mut inside = false;
        let n = ring.len();
        for i in 0..n {
            let [x1, y1] = ring[i];
            let [x2, y2] = ring[(i + 1) % n];
            if (y1 > lat) != (y2 > lat) && lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-12) + x1 {
                inside = !inside;
            }
        }
        if inside {
            return true;
        }
    }
    false
}
