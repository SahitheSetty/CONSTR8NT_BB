from app.collectors.traceroute import collect_traceroute


hops = collect_traceroute("github.com")

for hop in hops:
    print(hop.model_dump()) 