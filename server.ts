import express from 'express';
import path from 'path';
import fs from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import { createServer as createViteServer } from 'vite';

const execAsync = promisify(exec);

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  const getCalendarPath = () => {
    const primary = path.join(process.cwd(), 'kids_events.ics');
    if (fs.existsSync(primary)) return primary;
    const publicIcs = path.join(process.cwd(), 'public', 'kids_events.ics');
    if (fs.existsSync(publicIcs)) return publicIcs;
    return primary;
  };

  const getJsonPath = () => {
    const primary = path.join(process.cwd(), 'public', 'events.json');
    return primary;
  };

  // Serve the ICS calendar file directly for subscription / download
  const handleIcsDownload = (req: express.Request, res: express.Response) => {
    const icsPath = getCalendarPath();
    if (!fs.existsSync(icsPath)) {
      return res.status(404).send('Calendar file not generated yet. Run sync first.');
    }
    res.setHeader('Content-Type', 'text/calendar; charset=utf-8');
    res.setHeader('Content-Disposition', 'inline; filename="kids_events.ics"');
    res.setHeader('Cache-Control', 'public, max-age=3600');
    fs.createReadStream(icsPath).pipe(res);
  };

  app.get('/kids_events.ics', handleIcsDownload);
  app.get('/events.ics', handleIcsDownload);

  // API status endpoint
  app.get('/api/status', (req, res) => {
    const icsPath = getCalendarPath();
    const jsonPath = getJsonPath();
    let stats = null;
    let eventCount = 0;

    if (fs.existsSync(icsPath)) {
      const fileStat = fs.statSync(icsPath);
      const content = fs.readFileSync(icsPath, 'utf-8');
      const matches = content.match(/BEGIN:VEVENT/g);
      eventCount = matches ? matches.length : 0;
      stats = {
        exists: true,
        size: fileStat.size,
        updatedAt: fileStat.mtime.toISOString(),
        eventCount,
      };
    } else {
      stats = {
        exists: false,
        size: 0,
        updatedAt: null,
        eventCount: 0,
      };
    }

    res.json({
      status: 'ok',
      calendar: stats,
      hasScript: fs.existsSync(path.join(process.cwd(), 'sync_events.py')),
      hasWorkflow: fs.existsSync(path.join(process.cwd(), '.github', 'workflows', 'sync.yml')),
    });
  });

  // API to fetch parsed events
  app.get('/api/events', (req, res) => {
    const jsonPath = getJsonPath();
    if (fs.existsSync(jsonPath)) {
      try {
        const raw = fs.readFileSync(jsonPath, 'utf-8');
        const data = JSON.parse(raw);
        return res.json(data);
      } catch (err) {
        return res.status(500).json({ error: 'Failed to parse events JSON' });
      }
    }
    res.json({ generated_at: null, event_count: 0, events: [] });
  });

  // API to trigger sync execution and test the scraper live
  app.post('/api/trigger-sync', async (req, res) => {
    try {
      const startTime = Date.now();
      const { stdout, stderr } = await execAsync(
        'python3 sync_events.py --output kids_events.ics --json-output public/events.json --verbose',
        { cwd: process.cwd(), timeout: 60000 }
      );

      // Copy to public folder
      const icsPath = path.join(process.cwd(), 'kids_events.ics');
      if (fs.existsSync(icsPath)) {
        fs.mkdirSync(path.join(process.cwd(), 'public'), { recursive: true });
        fs.copyFileSync(icsPath, path.join(process.cwd(), 'public', 'kids_events.ics'));
        fs.copyFileSync(icsPath, path.join(process.cwd(), 'public', 'events.ics'));
      }

      const durationMs = Date.now() - startTime;
      const content = fs.existsSync(icsPath) ? fs.readFileSync(icsPath, 'utf-8') : '';
      const eventCount = (content.match(/BEGIN:VEVENT/g) || []).length;

      res.json({
        success: true,
        durationMs,
        eventCount,
        stdout,
        stderr,
      });
    } catch (err: any) {
      res.status(500).json({
        success: false,
        error: err.message || 'Scraper execution error',
        stdout: err.stdout || '',
        stderr: err.stderr || '',
      });
    }
  });

  // API to read sync_events.py and workflow code for in-app inspection
  app.get('/api/code-files', (req, res) => {
    try {
      const scriptPath = path.join(process.cwd(), 'sync_events.py');
      const workflowPath = path.join(process.cwd(), '.github', 'workflows', 'sync.yml');

      const scriptContent = fs.existsSync(scriptPath) ? fs.readFileSync(scriptPath, 'utf-8') : '';
      const workflowContent = fs.existsSync(workflowPath) ? fs.readFileSync(workflowPath, 'utf-8') : '';

      res.json({
        script: scriptContent,
        workflow: workflowContent,
      });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // Vite middleware in dev; static dist in production
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server listening on http://0.0.0.0:${PORT}`);
  });
}

startServer();
