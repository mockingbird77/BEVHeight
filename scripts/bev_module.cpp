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
			cout<< maxi << maxj<<endl;

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


    	return true;
    }

    void dfsSudoku(vector<vector<char>>& board, int r ,int c,int num ){

		// if(终止条件)
		
		if(r==maxi && c==maxj)  {valid = true; return;}


		for(int i = r; i < 9; i++ ){
			for(int j = c; j < 9; j++){
				if(board[i][j] =='.' && !valid){
					for(int k  = 1; k < 10; k++) //change to 1
					{
						if(isSudoku(i,j,k)){

							board[i][j] = '0'+k;
							row[i][k] ++;
							col[j][k] ++;
							sur[i/3][j/3][k] ++;

							dfsSudoku(board,i,j,k);
											
							if(valid) return;

							board[i][j] = '.';
							row[i][k]--;
							col[j][k]--;
							sur[i/3][j/3][k]--;
						}
					}
						return;
				}
			}

		}

	}

		

    
};

