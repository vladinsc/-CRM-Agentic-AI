"use client";

import { useState } from "react";

export default function SettingsPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGoogleConnect = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Citim URL-ul de backend din .env.
      // Fallback-ul este pus pentru siguranta in mediul de dezvoltare local.
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      
      // Apelam endpoint-ul pe care l-am construit in FastAPI
      const response = await fetch(`${apiUrl}/api/auth/google/login`);

      if (!response.ok) {
        throw new Error("Nu am putut contacta serverul. Verifica daca backend-ul ruleaza.");
      }

      const data = await response.json();

      // Daca backend-ul a returnat link-ul cu succes, redirectionam browserul
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error("URL-ul de autentificare lipseste din raspunsul serverului.");
      }
    } catch (err: any) {
      console.error("Eroare la conectarea cu Google:", err);
      setError(err.message || "A aparut o eroare la initierea autentificarii.");
      setIsLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Setari Platforma</h1>
        <p className="text-gray-600">
          Gestioneaza integrarile si preferintele contului tau de freelancer.
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Integrari</h2>
        
        <div className="flex items-center justify-between border border-gray-100 rounded-md p-4 bg-gray-50">
          <div>
            <h3 className="font-medium text-gray-900">Google Workspace (Gmail)</h3>
            <p className="text-sm text-gray-500 mt-1">
              Conecteaza-ti contul de Gmail pentru a sincroniza mesajele clientilor direct in CRM.
            </p>
          </div>
          
          <button
            onClick={handleGoogleConnect}
            disabled={isLoading}
            className={`px-4 py-2 rounded-md font-medium text-white transition-colors flex items-center gap-2
              ${isLoading 
                ? "bg-blue-400 cursor-not-allowed" 
                : "bg-blue-600 hover:bg-blue-700 active:bg-blue-800"
              }`}
          >
            {isLoading ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Se conecteaza...
              </>
            ) : (
              "Conecteaza Gmail"
            )}
          </button>
        </div>

        {/* Afisarea erorilor in caz ca API-ul pica */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-600 rounded-md text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}