import requests
import time

SPANSH_ROUTE_URL = "https://spansh.co.uk/api/route"
SPANSH_RESULTS_URL = "https://spansh.co.uk/api/results/{job_id}"
SPANSH_SYSTEM_NAMES_URL = "https://spansh.co.uk/api/systems/field_values/system_names"

def lookup_system(query):
    """Match a typed name against Spansh's system list.

    Returns (exact_name, suggestions): exact_name is the canonical spelling
    when the query matches a system (ignoring case), otherwise None, with up
    to 6 close names in suggestions. Typos with no close match return
    (None, []).
    """
    response = requests.get(SPANSH_SYSTEM_NAMES_URL, params={"q": query}, timeout=15)
    response.raise_for_status()
    names = response.json().get("values", [])
    for name in names:
        if name.lower() == query.strip().lower():
            return name, []
    return None, names[:6]

def plot_neutron_route(source, destination, jump_range, efficiency=60):
    params = {
        "efficiency": efficiency,
        "range": jump_range,
        "from": source,
        "to": destination,
    }

    response = requests.post(SPANSH_ROUTE_URL, params=params, timeout=15)
    response.raise_for_status()
    job_data = response.json()
    job_id = job_data.get("job")

    if not job_id:
        raise RuntimeError(f"Spansh did not return a job ID: {job_data}")

    for _ in range(30):
        time.sleep(1)
        result_resp = requests.get(SPANSH_RESULTS_URL.format(job_id=job_id), timeout=15)
        result_resp.raise_for_status()
        result_data = result_resp.json()

        if result_data.get("status") == "queued":
            continue

        result = result_data.get("result", {})
        return {
            "source": result.get("source_system", source),
            "destination": result.get("destination_system", destination),
            "range": float(result.get("range", jump_range)),
            "efficiency": int(result.get("efficiency", efficiency)),
            "distance": result.get("distance", 0),
            "job": job_id,
            "waypoints": [
                {
                    "system": j["system"],
                    "id64": j.get("id64"),
                    "jumps": j.get("jumps", 0),
                    "neutron_star": j.get("neutron_star", False),
                    "distance_left": j.get("distance_left", 0),
                }
                for j in result.get("system_jumps", [])
            ],
        }

    raise TimeoutError("Spansh route job did not complete in time")
