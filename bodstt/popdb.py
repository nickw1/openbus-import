# id deptime working origin destination
from pathlib import Path
from pytxc import Timetable
from pytxc.services import DayOfWeek
from functions import parse_run_time
import sys

class TimetableDatabase:

    def __init__(self, cur, timetable_dir):
        self.cur = cur
        self.stops = self.get_stops()
        self.day_of_week_list = list(DayOfWeek)
        self.timetable_dir = timetable_dir
        
    def populate(self,operator_code, date, service_code):
        globbed = Path(self.timetable_dir).glob(f"BODS_{operator_code}_{service_code}_{date}_*.xml")
        file = None
        for g in globbed:
            file = g

        if file is not None:
            timetable = Timetable.from_file_path(Path(file))

            for vj in timetable.vehicle_journeys:
                dep_time = vj.departure_time
                block_number = vj.operational.block.block_number if vj.operational.block else None
                jp = vj.journey_pattern_ref.resolve()
                dest = jp.destination_display
                direction = jp.direction
                operator = jp.operator_ref.resolve()
                op_prof = vj.operating_profile.days_of_week
                line = vj.line_ref.resolve().line_name
                run_days = [enumday.name[0:2].title() for enumday in op_prof]
                stmt=self.cur.execute("INSERT INTO journeys(working,route,operator_name,destination,deptime,run_days) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id", (block_number, line, operator.id, dest, dep_time, ",".join(run_days)))
                journey_id = self.cur.fetchone()[0]
        
                first_stop = None
                total_run_time = 0
                for tl in vj.timing_links:
                    timing_link = tl.journey_pattern_timing_link_ref.resolve()
                    start = timing_link.from_.stop_point_ref
                    if first_stop is None:
                        first_stop = start
                        try:
                            self.cur.execute("INSERT INTO journeystops(journeyid,stopid,reltime) VALUES(%s,%s,0)", (journey_id, self.stops[start][0]))
                            self.cur.execute("UPDATE journeys SET origin=%s WHERE id=%s", (",".join(self.stops[start][1:]), journey_id))
                        except KeyError as e:
                            print(f"Couldn't find ATCO code {start}", file=sys.stderr)
                    end = timing_link.to.stop_point_ref
                    run_time = parse_run_time(tl.run_time) 
                    total_run_time += run_time
                    try:
                        self.cur.execute("INSERT INTO journeystops(journeyid,stopid,reltime) VALUES(%s,%s,%s)", (journey_id, self.stops[end][0], total_run_time))
                    except KeyError as e:
                        print(f"Couldn't find ATCO code {end}", file=sys.stderr)
        else:
            print(f"Could not find BODS_{operator_code}_{service_code}_{date}_*.xml", file=sys.stderr)

    def get_stops(self):
        stops = {}
        self.cur.execute("SELECT atco_code, id, common_name, locality_name FROM stops")
        for row in self.cur:
            stops[row[0]] = row[1:]
        return stops
