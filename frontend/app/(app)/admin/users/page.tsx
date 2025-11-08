export default function AdminUsersPage(){
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Benutzerverwaltung</h1>
      <div className="card">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800">
              <th className="text-left py-2 px-3">ID</th>
              <th className="text-left py-2 px-3">Username</th>
              <th className="text-left py-2 px-3">Rolle</th>
              <th className="text-left py-2 px-3">Plan</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800">
              <td className="py-2 px-3" colSpan={4}>TODO: User-List</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
