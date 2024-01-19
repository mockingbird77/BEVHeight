class Solution {
public:

	int row[9][10];
	int col[9][10];
	int sur[3][3][10];
	int maxi;
    int maxj;
    bool valid;
	int level;

    void solveSudoku(vector<vector<char>>& board) {
    	//怎么判断他填充完了。


    	for(int i = 0; i < 9; i++ ){
	    		for(int j = 0; j < 9; j++){
	    			if(board[i][j] =='.'){
    					maxi = i;
    					maxj = j;
	    			}
					else{
						row[i][board[i][j]-'0']++;
    					col[j][board[i][j]-'0']++;
    					sur[i/3][j/3][board[i][j]-'0']++;
					}
		   		}
			}

    	for(int i = 0; i < 9; i++ ){
	    		for(int j = 0; j < 9; j++){
	    			if(board[i][j] == '.'){
							for(int k =1 ; k<= 9; k++)
								{if(!valid)
										{
											dfsSudoku(board,i,j,k);
										}}
							return;
	    			}
		   		}
			}
    }


    // 每添加一个就判断一次
    bool isSudoku(int i,int j,int num){
        // 
    	if(row[i][num] >= 1) return false;
    	if(col[j][num] >= 1) return false;
    	if(sur[i/3][j/3][num] >= 1) return false;

    	row[i][num] ++;
    	col[j][num] ++;
    	sur[i/3][j/3][num] ++;
    	return true;
    }

    void dfsSudoku(vector<vector<char>>& board, int r ,int c,int num ){
		level++;
		cout <<"level" << level << endl;
    	if(board[r][c] == '.' && !valid){
	    	if(isSudoku(r,c,num)){
	    		board[r][c] = '0'+num;
	    		if(r==maxi && c==maxj)  {valid = true; return;}
				bool flag = false;
		    	for(int i = r; i < 9; i++ ){
		    		for(int j = c; j < 9; j++){
		    			if(board[i][j] =='.' && !valid){
		    				for(int k=1; k<10; k++) //change to 1
		    				{
		    					dfsSudoku(board,i,j,k);
		    				}
								flag = true;
								break;
		    			}
							if(flag) 
								break;
		    		}
					if(flag) 
						break;
		    	}
		    	if(valid) return;
				cout<<"......"<<endl;
				cout<<"num"<<num<<endl;
		    	board[r][c] = '.';
    			row[r][num]--;
	    		col[c][num]--;
	    		sur[r/3][c/3][num]--;
		    }
		    else {level--; return;}
		}
		level--;
    }
};

