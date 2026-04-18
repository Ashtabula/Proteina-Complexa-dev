const fs = require('fs');

const path = 'Proteina_Complexa_coLab.ipynb';
const data = JSON.parse(fs.readFileSync(path, 'utf8'));

let cell_10 = data.cells[10];
let source_10 = cell_10.source;

for (let i = 0; i < source_10.length; i++) {
    source_10[i] = source_10[i].replace('"Top_Max_ipSAE", "Status"', '"Overall_Data_Link", "Status"');
    source_10[i] = source_10[i].replace('Top_Max_ipSAE (留空给 Cell 7 更新)', 'Overall_Data_Link (留空给 Cell 7 更新)');
}

cell_10.source = source_10;

fs.writeFileSync(path, JSON.stringify(data, null, 1), 'utf8');
console.log("Patch applied successfully.");
