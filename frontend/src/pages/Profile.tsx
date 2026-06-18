import React, { useEffect, useState, useRef } from 'react';
import api from '../lib/api';
import { User, FileText, Check, AlertCircle, UploadCloud } from 'lucide-react';

export const Profile: React.FC = () => {
  const [profile, setProfile] = useState<any>(null);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [country, setCountry] = useState('Brazil');
  const [zipCode, setZipCode] = useState('');
  const [cpf, setCpf] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [portfolioUrl, setPortfolioUrl] = useState('');
  const [currentTitle, setCurrentTitle] = useState('');
  const [currentCompany, setCurrentCompany] = useState('');
  const [resumeName, setResumeName] = useState<string | null>(null);
  
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchProfile = async () => {
    try {
      const res = await api.get('/api/profile');
      setProfile(res.data);
      setFirstName(res.data.first_name || '');
      setLastName(res.data.last_name || '');
      setEmail(res.data.email || '');
      setPhone(res.data.phone || '');
      setCity(res.data.city || '');
      setState(res.data.state || '');
      setCountry(res.data.country || 'Brazil');
      setZipCode(res.data.zip_code || '');
      setCpf(res.data.cpf || '');
      setLinkedinUrl(res.data.linkedin_url || '');
      setGithubUrl(res.data.github_url || '');
      setPortfolioUrl(res.data.portfolio_url || '');
      setCurrentTitle(res.data.current_title || '');
      setCurrentCompany(res.data.current_company || '');
      
      if (res.data.resume_path) {
        setResumeName(res.data.resume_path.split(/[/\\]/).pop());
      }
    } catch (err) {
      console.error('Failed to load profile:', err);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    const payload = {
      first_name: firstName,
      last_name: lastName,
      email,
      phone,
      city,
      state,
      country,
      zip_code: zipCode,
      cpf,
      linkedin_url: linkedinUrl,
      github_url: githubUrl,
      portfolio_url: portfolioUrl,
      current_title: currentTitle,
      current_company: currentCompany
    };

    try {
      await api.put('/api/profile', payload);
      alert('Profile updated successfully.');
    } catch (err) {
      alert('Failed to update profile.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      alert('Please select only PDF files for your resume.');
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/api/profile/resume', formData, {
        headers: { 'Content-Type': undefined }
      });
      if (res.data.resume_path) {
        setResumeName(res.data.resume_path.split(/[/\\]/).pop());
      }
      alert('Resume PDF uploaded successfully!');
    } catch (err) {
      alert('Failed to upload resume.');
    } finally {
      setIsUploading(false);
    }
  };

  if (!profile) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-500 text-xs italic">
        Loading profile...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div>
        <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <User className="w-5 h-5 text-primary-600" />
          My Profile Details
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          This information will be used by the bot to automatically fill Easy Apply forms.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Form (2 cols) */}
        <div className="md:col-span-2 p-6 glass-panel border-slate-200">
          <form onSubmit={handleSaveProfile} className="space-y-6 bg-white">
            
            {/* Basic Info Section */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Basic Information</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">First Name</label>
                  <input
                    type="text"
                    required
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Last Name</label>
                  <input
                    type="text"
                    required
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Email Address</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Phone Number</label>
                  <input
                    type="tel"
                    required
                    placeholder="+55 11 9xxxx-xxxx"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Location Section */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Location</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">City</label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">State / Province</label>
                  <input
                    type="text"
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">ZIP / Postal Code</label>
                  <input
                    type="text"
                    value={zipCode}
                    onChange={(e) => setZipCode(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Country</label>
                  <input
                    type="text"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">CPF Document</label>
                  <input
                    type="text"
                    placeholder="e.g. 123.456.789-00"
                    value={cpf}
                    onChange={(e) => setCpf(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Professional Profiles */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Professional Profiles</h3>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">LinkedIn Profile URL</label>
                  <input
                    type="url"
                    value={linkedinUrl}
                    onChange={(e) => setLinkedinUrl(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">GitHub Profile URL</label>
                  <input
                    type="url"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Portfolio / Website URL</label>
                  <input
                    type="url"
                    value={portfolioUrl}
                    onChange={(e) => setPortfolioUrl(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Employment Status */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Current Employment</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Job Title / Role</label>
                  <input
                    type="text"
                    value={currentTitle}
                    onChange={(e) => setCurrentTitle(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Company Name</label>
                  <input
                    type="text"
                    value={currentCompany}
                    onChange={(e) => setCurrentCompany(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSaving}
              className="w-full glass-btn-primary py-2.5 font-semibold"
            >
              <Check className="w-4 h-4" />
              {isSaving ? 'Saving Changes...' : 'Save Profile'}
            </button>
          </form>
        </div>

        {/* Right Upload Column */}
        <div className="space-y-6">
          <div className="p-6 glass-panel border-slate-200 flex flex-col items-center text-center bg-white">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Resume PDF</h3>
            
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleResumeUpload}
              accept=".pdf"
              className="hidden"
            />
            
            <div 
              onClick={() => fileInputRef.current?.click()}
              className="w-full border-2 border-dashed border-slate-200 hover:border-primary-500/50 rounded-xl p-8 cursor-pointer bg-slate-50 hover:bg-primary-50/20 transition-all duration-200 flex flex-col items-center justify-center gap-3"
            >
              <UploadCloud className="w-10 h-10 text-slate-400 hover:text-primary-600 transition-colors" />
              <div>
                <p className="text-xs font-semibold text-slate-700">Upload New Resume</p>
                <p className="text-[10px] text-slate-400 mt-1">PDF format only (Max 5MB)</p>
              </div>
            </div>

            {resumeName ? (
              <div className="w-full mt-6 bg-slate-50 p-4 border border-slate-200 rounded-lg flex items-start gap-3 text-left">
                <FileText className="w-8 h-8 text-primary-600 flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-slate-800 truncate">{resumeName}</p>
                  <span className="text-[9px] text-emerald-600 font-bold flex items-center gap-1 mt-1">
                    <Check className="w-3 h-3" /> Active Resume
                  </span>
                </div>
              </div>
            ) : (
              <div className="w-full mt-6 p-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-start gap-2 text-left">
                <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
                <p>No active resume uploaded. The bot cannot apply to jobs without a configured PDF resume.</p>
              </div>
            )}
            
            {isUploading && (
              <p className="text-[10px] text-primary-600 animate-pulse mt-3 font-semibold">Uploading resume...</p>
            )}
          </div>
        </div>

      </div>

    </div>
  );
};
