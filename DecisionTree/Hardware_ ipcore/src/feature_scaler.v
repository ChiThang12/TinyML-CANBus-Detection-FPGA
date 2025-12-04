module feature_scaler (
    input  wire        clk,              // Thêm clock để pipeline
    input  wire        rst_n,
    input  wire        valid_in,         // Input valid signal
    input  wire [10:0] arb_id_dec,
    input  wire [3:0]  data_length,
    input  wire [7:0]  first_byte,
    input  wire [7:0]  last_byte,
    input  wire [10:0] byte_sum,
    input  wire [31:0] time_delta,
    
    output reg  [31:0] feature_0_scaled,
    output reg  [31:0] feature_1_scaled,
    output reg  [31:0] feature_2_scaled,
    output reg  [31:0] feature_3_scaled,
    output reg  [31:0] feature_4_scaled,
    output reg  [31:0] feature_5_scaled,
    output reg         valid_out         // Output valid signal
);

    // Pipeline registers để tránh timing violations
    reg [31:0] f0_comb, f1_comb, f2_comb, f3_comb, f4_comb, f5_comb;
    
    // Combinational scaling
    always @(*) begin
        // Feature 0: arb_id_dec - Q11.16
        f0_comb = {21'b0, arb_id_dec} << 16;
        
        // Feature 1: data_length - Q4.23
        f1_comb = {28'b0, data_length} << 23;
        
        // Feature 2: first_byte - Q8.19
        f2_comb = {24'b0, first_byte} << 19;
        
        // Feature 3: last_byte - Q8.19
        f3_comb = {24'b0, last_byte} << 19;
        
        // Feature 4: byte_sum - Q11.16
        f4_comb = {21'b0, byte_sum} << 16;
        
        // Feature 5: time_delta - Q0.27
        // Sử dụng phép nhân thay vì chia để tránh latency cao
        // time_delta (us) * 2^27 / 1000000 ≈ time_delta * 134
        f5_comb = (time_delta * 134);  // Approximate scaling
    end
    
    // Sequential output để đồng bộ timing
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            feature_0_scaled <= 32'b0;
            feature_1_scaled <= 32'b0;
            feature_2_scaled <= 32'b0;
            feature_3_scaled <= 32'b0;
            feature_4_scaled <= 32'b0;
            feature_5_scaled <= 32'b0;
            valid_out <= 1'b0;
        end else if (valid_in) begin
            feature_0_scaled <= f0_comb;
            feature_1_scaled <= f1_comb;
            feature_2_scaled <= f2_comb;
            feature_3_scaled <= f3_comb;
            feature_4_scaled <= f4_comb;
            feature_5_scaled <= f5_comb;
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule
