import datetime as dt
import unittest
from thermal_guard import ROOT, cpu_reading, hot, workload


class ThermalTests(unittest.TestCase):
    def test_threshold_edges(self):
        self.assertEqual(hot({'cpuC': 89.9, 'gpuC': 84.9}), [])
        self.assertEqual(hot({'cpuC': 90, 'gpuC': 85}), ['cpuC', 'gpuC'])
        self.assertEqual(hot({'cpuC': None, 'gpuC': 86}), ['gpuC'])

    def test_cpu_freshness_and_maximum(self):
        time = dt.datetime.now(dt.timezone.utc)
        sample = {'timestamp': time.isoformat(), 'sensors': [{'celsius': 65}, {'celsius': 91}]}
        self.assertEqual(cpu_reading(sample, time), 91)
        sample['sensors'].append({'name': 'P-Core #1 Distance to TjMax', 'celsius': 98})
        self.assertEqual(cpu_reading(sample, time), 91)
        with self.assertRaises(ValueError): cpu_reading(sample, time + dt.timedelta(seconds=91))
        sample['sensors'] = []
        with self.assertRaises(ValueError): cpu_reading(sample, time)

    def test_scope_excludes_os_other_apps_and_checker(self):
        def p(pid, parent, name, cmd):
            return dict(ProcessId=pid, ParentProcessId=parent, Name=name, CommandLine=cmd)
        rows = [p(1, 0, 'codex.exe', ''), p(2, 1, 'powershell.exe', ''),
                p(3, 2, 'python.exe', str(ROOT)+'/apps/video/thermal_guard.py'),
                p(10, 1, 'python.exe', str(ROOT)+'/apps/video/render_selected_shorts.py'),
                p(11, 10, 'ffmpeg.exe', 'ffmpeg -i relative.mp4'),
                p(12, 1, 'AoE2DE_s.exe', 'game'), p(20, 1, 'python.exe', 'C:/other/project.py'),
                p(21, 1, 'explorer.exe', str(ROOT))]
        self.assertEqual({p['ProcessId'] for p in workload(rows, 3)}, {10, 11, 12})


if __name__ == '__main__': unittest.main()
