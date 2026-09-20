import React, { useState, useEffect } from 'react';
import { Copy, Check, FileCode, GitBranch, ShieldCheck, Terminal, BookOpen } from 'lucide-react';

export const WorkflowViewer: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'workflow' | 'script' | 'security'>('workflow');
  const [scriptCode, setScriptCode] = useState('');
  const [workflowCode, setWorkflowCode] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch('/api/code-files')
      .then((res) => res.json())
      .then((data) => {
        if (data.script) setScriptCode(data.script);
        if (data.workflow) setWorkflowCode(data.workflow);
      })
      .catch((err) => console.error('Error loading files:', err));
  }, []);

  const currentContent = activeTab === 'workflow' ? workflowCode : scriptCode;

  const handleCopy = () => {
    navigator.clipboard.writeText(currentContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white rounded-2xl border border-stone-200 shadow-xs overflow-hidden">
      <div className="border-b border-stone-200 bg-stone-50/50 p-4 sm:px-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            id="tab-workflow-btn"
            onClick={() => setActiveTab('workflow')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'workflow'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'bg-white text-stone-600 hover:text-stone-900 border border-stone-200'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" />
            .github/workflows/sync.yml
          </button>

          <button
            id="tab-script-btn"
            onClick={() => setActiveTab('script')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'script'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'bg-white text-stone-600 hover:text-stone-900 border border-stone-200'
            }`}
          >
            <FileCode className="w-3.5 h-3.5" />
            sync_events.py
          </button>

          <button
            id="tab-security-btn"
            onClick={() => setActiveTab('security')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === 'security'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'bg-white text-stone-600 hover:text-stone-900 border border-stone-200'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            Security & Setup Guide
          </button>
        </div>

        {activeTab !== 'security' && (
          <button
            id="copy-code-btn"
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white hover:bg-stone-50 text-stone-700 border border-stone-300 rounded-lg transition-colors shadow-xs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 text-stone-500" />}
            {copied ? 'Copied to Clipboard!' : 'Copy File Content'}
          </button>
        )}
      </div>

      {activeTab === 'security' ? (
        <div className="p-6 space-y-6 text-sm text-stone-700 leading-relaxed">
          <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-4">
            <h4 className="font-semibold text-amber-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-amber-700" />
              Security Architecture & Secrets Management
            </h4>
            <p className="text-xs text-amber-800 mt-1.5">
              The scraper and GitHub Actions workflow are built with security-first design principles:
            </p>
            <ul className="mt-2 text-xs text-amber-800 space-y-1 list-disc list-inside">
              <li><strong>Zero third-party hardcoded tokens:</strong> Public website scraping uses Python standard library without API keys.</li>
              <li><strong>Least Privilege Git Permissions:</strong> The workflow limits permissions strictly to <code>contents: write</code>.</li>
              <li><strong>Automated Encrypted Tokens:</strong> Pushes are signed using GitHub Actions' built-in encrypted token <code>{"${{ secrets.GITHUB_TOKEN }}"}</code>.</li>
              <li><strong>Encrypted Optional Webhooks:</strong> Any notification webhook (Discord, Slack, or Healthchecks.io) reads exclusively from encrypted repository secrets.</li>
            </ul>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-stone-900 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-stone-600" />
              How to Deploy to GitHub
            </h4>
            <ol className="list-decimal list-inside text-xs text-stone-600 space-y-2">
              <li>Push this repository to GitHub containing <code>sync_events.py</code> and <code>.github/workflows/sync.yml</code>.</li>
              <li>In your GitHub repo settings, ensure <strong>Settings &gt; Actions &gt; General &gt; Workflow permissions</strong> is set to <em>&ldquo;Read and write permissions&rdquo;</em> (needed for the bot to push the updated <code>kids_events.ics</code> calendar file).</li>
              <li>If using an optional monitoring or notification webhook, navigate to <strong>Settings &gt; Secrets and variables &gt; Actions</strong> and add secret <code>SYNC_WEBHOOK_URL</code>.</li>
              <li>The workflow will automatically run every day at 06:00 UTC (02:00 AM EDT / 01:00 AM EST) and can also be triggered manually under the <strong>Actions</strong> tab anytime.</li>
            </ol>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-stone-900 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-stone-600" />
              Running & Testing Locally
            </h4>
            <div className="bg-stone-900 text-stone-200 p-3.5 rounded-xl font-mono text-xs overflow-x-auto space-y-1">
              <div># Run the scraper and generate kids_events.ics:</div>
              <div className="text-emerald-400">python3 sync_events.py --output kids_events.ics --verbose</div>
              <div className="mt-2"># Dry run mode (validates without writing files):</div>
              <div className="text-emerald-400">python3 sync_events.py --dry-run</div>
            </div>
          </div>
        </div>
      ) : (
        <div className="relative">
          <pre className="p-4 bg-stone-900 text-stone-100 font-mono text-xs overflow-x-auto max-h-[500px] leading-relaxed">
            {currentContent || 'Loading file content...'}
          </pre>
        </div>
      )}
    </div>
  );
};
