'use client'

import { useState, useEffect } from 'react'
import { 
  Search, 
  Filter, 
  ListFilter, 
  X, 
  ChevronDown, 
  ChevronUp, 
  FileText, 
  Folder, 
  CalendarDays, 
  Database, 
  Copy, 
  Eye, 
  Download, 
  HardDrive, 
  BarChart3,
  RefreshCcwIcon,
  AlertTriangle,
  CheckCircle2,
  InfoIcon,
  CalendarPlus, 
  Trash2,       
  ListChecks    
} from 'lucide-react'; 
import toast, { Toaster } from 'react-hot-toast' 
import axios from 'axios'
import { format } from 'date-fns'

interface SearchRequest {
  extensions?: string[]
  min_size: number
  max_size?: number
  min_date?: string
  max_date?: string
  partial_names?: string[]
  match_logic: 'or' | 'and'
  search_terms?: string[]
  case_sensitive: boolean
  owner_filter?: string
  duplicates_only: boolean
  limit: number
}

interface FileResult {
  id: number
  file_path: string
  file_name: string
  file_extension: string
  file_size: number
  creation_date: string
  modified_date: string
  owner: string
  content_hash: string
  is_text_file: boolean
}

interface IndexingStatus {
  last_index_date: string | null
  total_files_indexed: number
  indexing_in_progress: boolean
  current_directory: string | null
  progress_percentage: number
}

interface Statistics {
  total_files: number
  text_files: number
  total_size: number
  top_extensions: Array<{ extension: string; count: number }>
}

interface Schedule {
  id: number;
  job_id: string;
  root_path: string;
  cron_expression: string;
  force_reindex: boolean;
  description?: string;
  created_at: string; 
}

interface ScheduleFormData {
  root_path: string;
  cron_expression: string;
  force_reindex: boolean;
  description: string;
}

export default function HomePage() {
  const [searchParams, setSearchParams] = useState<SearchRequest>({
    extensions: [],
    min_size: 0,
    max_size: undefined,
    min_date: undefined,
    max_date: undefined,
    partial_names: [],
    match_logic: 'or',
    search_terms: [],
    case_sensitive: false,
    owner_filter: undefined,
    duplicates_only: false,
    limit: 1000
  })

  const [results, setResults] = useState<FileResult[]>([])
  const [loading, setLoading] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);

  // State for Scheduled Indexing
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [scheduleFormData, setScheduleFormData] = useState<ScheduleFormData>({
    root_path: '',
    cron_expression: '',
    force_reindex: false,
    description: '',
  });
  const [isLoadingSchedules, setIsLoadingSchedules] = useState(false);
  const [isSubmittingSchedule, setIsSubmittingSchedule] = useState(false);
  const [indexingStatus, setIndexingStatus] = useState<IndexingStatus | null>(null)
  const [statistics, setStatistics] = useState<Statistics | null>(null)
  const [activeTab, setActiveTab] = useState<'search' | 'index' | 'stats'>('search')
  const [indexPath, setIndexPath] = useState('/home')
  const [previewFile, setPreviewFile] = useState<FileResult | null>(null); 
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Form state
  const [extensionsInput, setExtensionsInput] = useState('')
  const [partialNamesInput, setPartialNamesInput] = useState('')
  const [searchTermsInput, setSearchTermsInput] = useState('')
  const [minSizeInput, setMinSizeInput] = useState('')
  const [maxSizeInput, setMaxSizeInput] = useState('')
  const [minDateInput, setMinDateInput] = useState('')
  const [maxDateInput, setMaxDateInput] = useState('')

  useEffect(() => {
    fetchIndexingStatus()
    fetchStatistics()
    const interval = setInterval(() => {
      fetchIndexingStatus()
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  const fetchIndexingStatus = async () => {
    try {
      const response = await axios.get('/api/status')
      setIndexingStatus(response.data)
    } catch (error) {
      console.error('Error fetching status:', error)
    }
  }

  const fetchStatistics = async () => {
    try {
      const response = await axios.get('/api/statistics')
      setStatistics(response.data)
    } catch (error) {
      console.error('Error fetching statistics:', error)
    }
  }

  const handleSearch = async () => {
    setLoading(true)
    try {
      const searchRequest: SearchRequest = {
        ...searchParams,
        extensions: extensionsInput ? extensionsInput.split(',').map(s => s.trim()).filter(Boolean) : undefined,
        partial_names: partialNamesInput ? partialNamesInput.split(',').map(s => s.trim()).filter(Boolean) : undefined,
        search_terms: searchTermsInput ? searchTermsInput.split(',').map(s => s.trim()).filter(Boolean) : undefined,
        min_size: minSizeInput ? parseInt(minSizeInput) : 0,
        max_size: maxSizeInput ? parseInt(maxSizeInput) : undefined,
        min_date: minDateInput || undefined,
        max_date: maxDateInput || undefined
      }

      const response = await axios.post('/api/search', searchRequest)
      setResults(response.data.results)
      toast.success(`Found ${response.data.count} files`)
    } catch (error) {
      toast.error('Search failed')
      console.error('Search error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleStartIndexing = async (forceReindex = false) => {
    let toastId: string | number | undefined;
    try {
      toastId = toast.loading(forceReindex ? 'Starting force re-index...' : 'Starting indexing...');
      const response = await axios.post('/api/index', { root_path: indexPath, force_reindex: forceReindex });
      toast.success(response.data.message || (forceReindex ? 'Force re-index started!' : 'Indexing started!'), { id: String(toastId) });
      fetchIndexingStatus()
    } catch (error: any) {
      toast.error(`Error: ${error.response?.data?.detail || 'Failed to start indexing'}`, { id: String(toastId), duration: 5000 });
    }
  }

  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    if (bytes === 0) return '0 Bytes'
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  const exportResults = () => {
    if (results.length === 0) {
      toast.error('No results to export')
      return
    }

    const csv = [
      ['File Path', 'File Name', 'Size', 'Modified Date', 'Owner', 'Extension'].join(','),
      ...results.map(file => [
        `"${file.file_path}"`,
        `"${file.file_name}"`,
        file.file_size,
        file.modified_date,
        file.owner,
        file.file_extension || ''
      ].join(','))
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `search_results_${format(new Date(), 'yyyy-MM-dd_HH-mm-ss')}.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('Results exported')
  }

  // --- Scheduled Indexing API Functions ---
  const fetchSchedules = async () => {
    setIsLoadingSchedules(true);
    try {
      const response = await fetch('/api/schedules');
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch schedules');
      }
      const data: Schedule[] = await response.json();
      setSchedules(data);
    } catch (error: any) {
      toast.error(`Error fetching schedules: ${error.message}`);
      console.error('Fetch schedules error:', error);
    }
    setIsLoadingSchedules(false);
  };

  const handleCreateSchedule = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!scheduleFormData.root_path.trim() || !scheduleFormData.cron_expression.trim()) {
      toast.error('Root path and CRON expression are required.');
      return;
    }
    setIsSubmittingSchedule(true);
    try {
      const response = await fetch('/api/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(scheduleFormData),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create schedule');
      }
      toast.success('Schedule created successfully!');
      setScheduleFormData({ root_path: '', cron_expression: '', force_reindex: false, description: '' });
      fetchSchedules(); // Refresh the list
    } catch (error: any) {
      toast.error(`Error creating schedule: ${error.message}`);
      console.error('Create schedule error:', error);
    }
    setIsSubmittingSchedule(false);
  };

  const handleDeleteSchedule = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this schedule?')) return;
    try {
      const response = await fetch(`/api/schedules/${jobId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete schedule');
      }
      toast.success('Schedule deleted successfully!');
      fetchSchedules(); // Refresh the list
    } catch (error: any) {
      toast.error(`Error deleting schedule: ${error.message}`);
      console.error('Delete schedule error:', error);
    }
  };

  // Fetch schedules on component mount
  useEffect(() => {
    if (activeTab === 'index') { // Only fetch if index tab is active, or fetch always if preferred
      fetchSchedules();
    }
  }, [activeTab]); // Re-fetch if tab changes to index, or remove activeTab dependency to fetch once

  // Function to handle copying text to clipboard
  const handleCopy = (text: string) => {
    if (!text) return;
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text)
        .then(() => toast.success('Copied to clipboard!'))
        .catch(() => fallbackCopyTextToClipboard(text));
    } else {
      fallbackCopyTextToClipboard(text);
    }
  };

  // Fallback for copying text if navigator.clipboard is not available
  function fallbackCopyTextToClipboard(text: string) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed"; // Prevent scrolling to bottom of page in MS Edge.
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.opacity = "0"; // Hide the textarea
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      toast.success('Copied to clipboard!');
    } catch (err) {
      toast.error('Failed to copy');
      console.error('Fallback: Oops, unable to copy', err);
    }
    document.body.removeChild(textArea);
  }

  const handlePreview = async (file: FileResult) => {
    console.log('[Preview Debug] File received by handlePreview:', JSON.parse(JSON.stringify(file)));
    setPreviewFile(file); // Show modal with metadata immediately
    setIsPreviewLoading(true);
    setPreviewContent(null); // Clear previous content

    if (!file.is_text_file) {
      console.log('[Preview Debug] Frontend identifies file as non-text. Path:', file.file_path);
      setPreviewContent('Preview not available for binary files (as identified by frontend).');
      setIsPreviewLoading(false);
      return;
    }

    // If frontend thinks it's a text file, try fetching content
    try {
      toast.loading('Loading preview...', { id: 'preview-toast' });
      const response = await axios.get<{ file_path: string; content: string | null; is_text_file: boolean; message?: string }>(
        `/api/file-content?file_path=${encodeURIComponent(file.file_path)}`
      );
      console.log('[Preview Debug] API Response Data:', JSON.parse(JSON.stringify(response.data)));
      
      if (response.data) {
        if (response.data.is_text_file && response.data.content !== null) {
          setPreviewContent(response.data.content);
          console.log('[Preview Debug] Setting previewContent (actual content):', response.data.content);
          toast.success('Preview loaded!', { id: 'preview-toast' });
        } else if (response.data.is_text_file && response.data.content === null) { // Explicitly null content for a text file
          setPreviewContent("<content is null according to backend>");
          console.log('[Preview Debug] Setting previewContent (content is null from backend).');
          toast.success('Preview loaded (content is null).', { id: 'preview-toast' });
        } else if (!response.data.is_text_file) {
          setPreviewContent(response.data.message || 'File identified as non-text by backend.');
          console.log('[Preview Debug] Setting previewContent (non-text from backend):', response.data.message || 'File identified as non-text by backend.');
          toast(response.data.message || 'File identified as non-text by backend.', { id: 'preview-toast', icon: '⚠️' });
        } else { // Should not be reached if backend response is well-formed
          setPreviewContent("Unexpected response format for content.");
          console.log('[Preview Debug] Setting previewContent (unexpected response format).');
          toast.error("Unexpected response for preview.", { id: 'preview-toast' });
        }
      } else {
        console.error('[Preview Debug] Empty response from server for file:', file.file_path);
        throw new Error("Empty response from server");
      }
    } catch (error: any) {
      console.error('[Preview Debug] Error fetching file content for path:', file.file_path, error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to load file content.';
      setPreviewContent(`Error: ${errorMessage}`);
      console.log('[Preview Debug] Setting previewContent (error):', `Error: ${errorMessage}`);
      toast.error(`Preview failed: ${errorMessage}`, { id: 'preview-toast' });
    } finally {
      setIsPreviewLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 text-gray-100 p-4 md:p-8 font-sans">
      <Toaster position="top-right" /> {/* Added Toaster for notifications */}
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <Search className="h-8 w-8 text-primary-600" />
              <h1 className="text-2xl font-bold text-gray-900">O2FileSearchPlus Enhanced</h1>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex bg-gray-100 rounded-lg p-1">
                <button
                  onClick={() => setActiveTab('search')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'search' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <Search className="h-4 w-4 inline mr-2" />
                  Search
                </button>
                <button
                  onClick={() => setActiveTab('index')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'index' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <Database className="h-4 w-4 inline mr-2" />
                  Index
                </button>
                <button
                  onClick={() => setActiveTab('stats')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeTab === 'stats' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <BarChart3 className="h-4 w-4 inline mr-2" />
                  Statistics
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search Tab */}
        {activeTab === 'search' && (
          <div className="space-y-6">
            {/* Search Form */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4 flex items-center">
                <Filter className="h-5 w-5 mr-2" />
                Search Filters
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    File Extensions (comma separated)
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="txt, py, js, md"
                    value={extensionsInput}
                    onChange={(e) => setExtensionsInput(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Partial File Names
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="config, test, main"
                    value={partialNamesInput}
                    onChange={(e) => setPartialNamesInput(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Search Terms (content)
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="function, class, TODO"
                    value={searchTermsInput}
                    onChange={(e) => setSearchTermsInput(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Size (bytes)
                  </label>
                  <input
                    type="number"
                    className="input-field"
                    placeholder="0"
                    value={minSizeInput}
                    onChange={(e) => setMinSizeInput(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Size (bytes)
                  </label>
                  <input
                    type="number"
                    className="input-field"
                    placeholder="1048576"
                    value={maxSizeInput}
                    onChange={(e) => setMaxSizeInput(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Match Logic
                  </label>
                  <select
                    className="input-field"
                    value={searchParams.match_logic}
                    onChange={(e) => setSearchParams({...searchParams, match_logic: e.target.value as 'or' | 'and'})}
                  >
                    <option value="or">Any (OR)</option>
                    <option value="and">All (AND)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Date
                  </label>
                  <input
                    type="date"
                    className="input-field"
                    value={minDateInput}
                    onChange={(e) => setMinDateInput(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Date
                  </label>
                  <input
                    type="date"
                    className="input-field"
                    value={maxDateInput}
                    onChange={(e) => setMaxDateInput(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Result Limit
                  </label>
                  <input
                    type="number"
                    className="input-field"
                    value={searchParams.limit}
                    onChange={(e) => setSearchParams({...searchParams, limit: parseInt(e.target.value) || 1000})}
                  />
                </div>
              </div>

              <div className="flex items-center space-x-4 mt-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    checked={searchParams.case_sensitive}
                    onChange={(e) => setSearchParams({...searchParams, case_sensitive: e.target.checked})}
                  />
                  <span className="ml-2 text-sm text-gray-700">Case Sensitive</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    checked={searchParams.duplicates_only}
                    onChange={(e) => setSearchParams({...searchParams, duplicates_only: e.target.checked})}
                  />
                  <span className="ml-2 text-sm text-gray-700">Duplicates Only</span>
                </label>
              </div>

              <div className="flex justify-between items-center mt-6">
                <button
                  onClick={handleSearch}
                  disabled={loading}
                  className="btn-primary flex items-center"
                >
                  {loading ? (
                    <RefreshCcwIcon className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4 mr-2" />
                  )}
                  {loading ? 'Searching...' : 'Search Files'}
                </button>

                {results.length > 0 && (
                  <button
                    onClick={exportResults}
                    className="btn-secondary flex items-center"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                  </button>
                )}
              </div>
            </div>

            {/* Results */}
            {results.length > 0 && (
              <div className="card">
                <h2 className="text-lg font-semibold mb-4">
                  Search Results ({results.length} files)
                </h2>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          File
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Size
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Modified
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Owner
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Type
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {results.map((file) => (
                        <tr key={file.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              <FileText className="h-5 w-5 text-primary-400 mr-3 flex-shrink-0" />
                              <div>
                                <div className="text-sm font-medium text-gray-900">
                                  {file.file_name}
                                </div>
                                <div className="text-sm text-gray-500 truncate max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl">
                                  {file.file_path}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {formatFileSize(file.file_size)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {format(new Date(file.modified_date), 'MMM dd, yyyy HH:mm')}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {file.owner}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {file.file_extension || 'N/A'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 space-x-2">
                            <button 
                              onClick={() => handlePreview(file)}
                              className="p-1.5 text-blue-600 hover:text-blue-800 transition-colors duration-150 rounded-md hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
                              title="Preview File"
                            >
                              <Eye size={18} />
                            </button>
                            <button 
                              onClick={() => handleCopy(file.file_path)}
                              className="p-1.5 text-green-600 hover:text-green-800 transition-colors duration-150 rounded-md hover:bg-green-100 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-opacity-50"
                              title="Copy File Path"
                            >
                              <Copy size={18} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Index Tab */}
        {activeTab === 'index' && (
          <div className="space-y-6"> {/* Original outer div for Index tab */}
            {/* START: Original Manual Indexing Card */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4 flex items-center">
                <Database className="h-5 w-5 mr-2" />
                File Indexing
              </h2>

              {indexingStatus && (
                <div className="mb-6 p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-blue-900">
                      {indexingStatus.indexing_in_progress ? 'Indexing in progress...' : 'Indexing Status'}
                    </span>
                    <span className="text-sm text-blue-700">
                      {indexingStatus.progress_percentage.toFixed(1)}%
                    </span>
                  </div>
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{ width: `${indexingStatus.progress_percentage}%` }}
                    />
                  </div>
                  <div className="mt-2 text-sm text-blue-700">
                    {indexingStatus.last_index_date ? (
                      <p>Last indexed: {format(new Date(indexingStatus.last_index_date), 'MMM dd, yyyy HH:mm')}</p>
                    ) : (
                      <p>No previous indexing found</p>
                    )}
                    <p>Total files indexed: {indexingStatus.total_files_indexed?.toLocaleString() || 0}</p>
                    {indexingStatus.current_directory && (
                      <p className="truncate">Current: {indexingStatus.current_directory}</p>
                    )}
                  </div>
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Root Path to Index
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    value={indexPath}
                    onChange={(e) => setIndexPath(e.target.value)}
                    placeholder="/home/username"
                  />
                </div>

                <button
                  onClick={() => handleStartIndexing(false)}
                  disabled={indexingStatus?.indexing_in_progress}
                  className="btn-primary flex items-center"
                >
                  <Database className="h-4 w-4 mr-2" />
                  {indexingStatus?.indexing_in_progress ? 'Indexing...' : 'Start Indexing'}
                </button>

                <button
                  onClick={() => handleStartIndexing(true)} // Pass true for forceReindex
                  disabled={indexingStatus?.indexing_in_progress || !indexPath.trim()}
                  className="btn-secondary flex items-center mt-2" // Added mt-2 for spacing
                  title="Delete existing index data for this path and re-index from scratch."
                >
                  <RefreshCcwIcon className="h-4 w-4 mr-2" />
                  {indexingStatus?.indexing_in_progress ? 'Processing...' : 'Force Re-index Path'}
                </button>
              </div>
            </div>
            {/* END: Original Manual Indexing Card */}

            {/* START: New Scheduled Indexing Section */}
            <div className="mt-10 pt-6 border-t border-gray-300"> {/* Added to be a sibling of the "card" div */}
              <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                <ListChecks className="h-6 w-6 mr-2 text-primary-600" />
                Scheduled Indexing Jobs
              </h3>

              {/* Create Schedule Form */}
              <form onSubmit={handleCreateSchedule} className="mb-8 p-6 bg-white rounded-lg shadow-md space-y-4">
                <h4 className="text-lg font-medium text-gray-700 mb-3">Create New Schedule</h4>
                <div>
                  <label htmlFor="schedule_root_path" className="block text-sm font-medium text-gray-700">Root Path</label>
                  <input 
                    type="text" 
                    id="schedule_root_path"
                    className="input-field mt-1"
                    value={scheduleFormData.root_path}
                    onChange={(e) => setScheduleFormData({...scheduleFormData, root_path: e.target.value})}
                    placeholder="/path/to/your/documents"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="schedule_cron" className="block text-sm font-medium text-gray-700">CRON Expression</label>
                  <input 
                    type="text" 
                    id="schedule_cron"
                    className="input-field mt-1"
                    value={scheduleFormData.cron_expression}
                    onChange={(e) => setScheduleFormData({...scheduleFormData, cron_expression: e.target.value})}
                    placeholder="0 2 * * * (runs daily at 2 AM)"
                    required
                  />
                   <p className="mt-1 text-xs text-gray-500">
                    Need help? Try a <a href="https://crontab.guru/" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">CRON expression generator</a>.
                  </p>
                </div>
                <div>
                  <label htmlFor="schedule_description" className="block text-sm font-medium text-gray-700">Description (Optional)</label>
                  <input 
                    type="text" 
                    id="schedule_description"
                    className="input-field mt-1"
                    value={scheduleFormData.description}
                    onChange={(e) => setScheduleFormData({...scheduleFormData, description: e.target.value})}
                    placeholder="e.g., Daily backup documents indexing"
                  />
                </div>
                <div className="flex items-center">
                  <input 
                    type="checkbox" 
                    id="schedule_force_reindex"
                    className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    checked={scheduleFormData.force_reindex}
                    onChange={(e) => setScheduleFormData({...scheduleFormData, force_reindex: e.target.checked})}
                  />
                  <label htmlFor="schedule_force_reindex" className="ml-2 block text-sm text-gray-900">Force Re-index (deletes existing data for this path first)</label>
                </div>
                <button 
                  type="submit" 
                  className="btn-primary flex items-center"
                  disabled={isSubmittingSchedule}
                >
                  <CalendarPlus className="h-4 w-4 mr-2" />
                  {isSubmittingSchedule ? 'Creating...' : 'Create Schedule'}
                </button>
              </form>

              {/* List of Schedules */}
              <div>
                <h4 className="text-lg font-medium text-gray-700 mb-3">Existing Schedules</h4>
                {isLoadingSchedules ? (
                  <p>Loading schedules...</p>
                ) : schedules.length === 0 ? (
                  <p className="text-gray-600">No schedules found.</p>
                ) : (
                  <ul className="space-y-3">
                    {schedules.map((schedule) => (
                      <li key={schedule.job_id} className="p-4 bg-gray-50 rounded-md shadow-sm border border-gray-200">
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-semibold text-primary-700 truncate" title={schedule.root_path}>{schedule.root_path}</p>
                            <p className="text-sm text-gray-600">CRON: <code className="bg-gray-200 px-1 rounded">{schedule.cron_expression}</code></p>
                            {schedule.description && <p className="text-sm text-gray-500 italic">{schedule.description}</p>}
                            <p className="text-xs text-gray-500">Created: {format(new Date(schedule.created_at), 'MMM dd, yyyy HH:mm')}</p>
                            {schedule.force_reindex && <p className="text-xs text-orange-600 font-medium">Force Re-index: Yes</p>}
                          </div>
                          <button 
                            onClick={() => handleDeleteSchedule(schedule.job_id)} 
                            className="btn-danger-sm flex items-center p-2"
                            title="Delete Schedule"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            {/* END: New Scheduled Indexing Section */}
          </div>
        )}

        {/* Statistics Tab */}
        {activeTab === 'stats' && statistics && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="card">
                <div className="flex items-center">
                  <FileText className="h-8 w-8 text-primary-600" />
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">Total Files</p>
                    <p className="text-2xl font-bold text-gray-900">{statistics.total_files.toLocaleString()}</p>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="flex items-center">
                  <FileText className="h-8 w-8 text-green-600" />
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">Text Files</p>
                    <p className="text-2xl font-bold text-gray-900">{statistics.text_files.toLocaleString()}</p>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="flex items-center">
                  <HardDrive className="h-8 w-8 text-blue-600" />
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">Total Size</p>
                    <p className="text-2xl font-bold text-gray-900">{formatFileSize(statistics.total_size)}</p>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="flex items-center">
                  <BarChart3 className="h-8 w-8 text-purple-600" />
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">File Types</p>
                    <p className="text-2xl font-bold text-gray-900">{statistics.top_extensions.length}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="card">
              <h3 className="text-lg font-semibold mb-4">Top File Extensions</h3>
              <div className="space-y-2">
                {/*
                {statistics.top_extensions.map((ext, index) => (
                  <div key={ext.extension} className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900">
                      {ext.extension || '(no extension)'}
                    </span>
                    <div className="flex items-center space-x-2">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-primary-600 h-2 rounded-full" 

                        />
                      </div>
                      <span className="text-sm text-gray-600 w-16 text-right">
                        {ext.count.toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
                */}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Preview Modal */}
      {previewFile && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4 z-50 transition-opacity duration-300 ease-in-out">
          <div className="bg-slate-800 p-6 rounded-lg shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto text-gray-200 transform transition-all duration-300 ease-in-out scale-100">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-primary-400">File Preview</h3>
              <button 
                onClick={() => setPreviewFile(null)} 
                className="p-2 text-gray-400 hover:text-red-500 transition-colors duration-150 rounded-full hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-red-500"
                title="Close Preview"
              >
                <X size={24} />
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap">
                <strong className="w-1/4 font-medium text-gray-400">Name:</strong>
                <span className="w-3/4 break-words text-gray-100">{previewFile.file_name}</span>
              </div>
              <div className="flex flex-wrap">
                <strong className="w-1/4 font-medium text-gray-400">Path:</strong>
                <span className="w-3/4 break-words text-gray-100">{previewFile.file_path}</span>
              </div>
              <div className="flex">
                <strong className="w-1/4 font-medium text-gray-400">Size:</strong>
                <span className="w-3/4 text-gray-100">{formatFileSize(previewFile.file_size)}</span>
              </div>
              <div className="flex">
                <strong className="w-1/4 font-medium text-gray-400">Extension:</strong>
                <span className="w-3/4 text-gray-100">{previewFile.file_extension || 'N/A'}</span>
              </div>
              <div className="flex">
                <strong className="w-1/4 font-medium text-gray-400">Created:</strong>
                <span className="w-3/4 text-gray-100">{format(new Date(previewFile.creation_date), 'MMM dd, yyyy HH:mm:ss')}</span>
              </div>
              <div className="flex">
                <strong className="w-1/4 font-medium text-gray-400">Modified:</strong>
                <span className="w-3/4 text-gray-100">{format(new Date(previewFile.modified_date), 'MMM dd, yyyy HH:mm:ss')}</span>
              </div>
              <div className="flex">
                <strong className="w-1/4 font-medium text-gray-400">Owner:</strong>
                <span className="w-3/4 text-gray-100">{previewFile.owner}</span>
              </div>
              {previewFile.is_text_file && (
                 <div className="flex">
                    <strong className="w-1/4 font-medium text-gray-400">Text File:</strong>
                    <span className="w-3/4 text-gray-100">Yes</span>
                 </div>
              )}

              {/* File Content Preview Section */}
              <div className="mt-4 pt-4 border-t border-slate-700">
                <h4 className="text-md font-semibold text-gray-300 mb-2">File Content Preview:</h4>
                {isPreviewLoading ? (
                  <div className="text-center py-4">
                    <RefreshCcwIcon className="h-6 w-6 animate-spin inline-block text-primary-400" />
                    <p className="text-sm text-gray-400 mt-2">Loading content...</p>
                  </div>
                ) : previewContent !== null && previewContent !== undefined ? (
                  <pre className="bg-slate-950 p-3 rounded-md text-xs text-gray-200 whitespace-pre-wrap break-words max-h-[30vh] overflow-y-auto custom-scrollbar">
                    {previewContent === "" ? "<empty file>" : previewContent}
                  </pre>
                ) : (
                  <p className="text-sm text-gray-400 italic">
                    Content preview is not available or could not be loaded.
                  </p>
                )}
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button 
                onClick={() => handleCopy(previewFile.file_path)}
                className="btn-secondary flex items-center"
              >
                <Copy size={16} className="mr-2" />
                Copy Path
              </button>
              <button 
                onClick={() => setPreviewFile(null)} 
                className="btn-primary flex items-center"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
